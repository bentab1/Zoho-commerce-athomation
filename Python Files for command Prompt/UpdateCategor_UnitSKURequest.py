import requests
import time
import pandas as pd
from slugify import slugify

# -------------------------------
# CONFIGURATION
# -------------------------------
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
org_id = "891730368"
LOG_FILE = "Update Category_Unit_withSKURequest.ipynb_Log.xlsx"

# -------------------------------
# GET ACCESS TOKEN
# -------------------------------
def get_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, params=params)
    data = response.json()
    return data.get("access_token")

# -------------------------------
# GET SKU LIST
# -------------------------------
def get_sku_list():
    mode = input("Choose SKU input mode:\n1 - Generate SKUs\n2 - Provide SKU list (comma separated)\nEnter choice (1 or 2): ").strip()
    if mode == "1":
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (e.g. IP): ").strip()
        start = int(input("Enter start number (e.g. 1): ").strip())
        end = int(input("Enter end number (e.g. 10): ").strip())
        mid_code = item_name.upper()[:2]

        pad_option = input("Choose padding type:\n1 - Fixed 6-digit zero padding (e.g. 000065)\n2 - No padding (e.g. 563)\n3 - Dynamic padding based on input\nEnter choice (1, 2, or 3): ").strip()

        if pad_option == "1":
            pad_len = 6
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
        elif pad_option == "2":
            skus = [f"{prefix}-{mid_code}-{str(num)}" for num in range(start, end + 1)]
        elif pad_option == "3":
            pad_len = max(len(str(start)), len(str(end)))
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
        else:
            print("Invalid padding option. Exiting.")
            exit()

        print(f"Generated SKUs: {skus}")
        return skus

    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
        print(f"Using provided SKUs: {skus}")
        return skus
    else:
        print("Invalid mode. Exiting.")
        exit()

# -------------------------------
# GET PRODUCT BY SKU
# -------------------------------
def get_product_by_sku(sku, access_token, org_id):
    sku = sku.strip().upper()  # normalize search input

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": org_id
    }
    url = f"https://commerce.zoho.com/store/api/v1/products?organization_id={org_id}&search_text={sku}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to fetch products: {response.status_code} {response.text}")
        return None, None

    products = response.json().get("products", [])

    # First check exact SKU matches for main products
    for product in products:
        prod_sku = str(product.get("sku", "")).strip().upper()
        if prod_sku == sku:
            return product, None

    # Then check exact SKU matches for variants
    for product in products:
        for variant in product.get("variants", []):
            var_sku = str(variant.get("sku", "")).strip().upper()
            if var_sku == sku:
                return variant, product  # return variant + its parent product

    # No exact match found
    return None, None


# -------------------------------
# GET CATEGORY ID FROM NAME
# -------------------------------
def get_category_id_from_name(access_token, org_id, category_name):
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": org_id
    }
    url = f"https://commerce.zoho.com/store/api/v1/categories?organization_id={org_id}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch categories: {response.status_code} {response.text}")
        return None
    data = response.json()
    categories = data.get("categories", [])
    cat_name_to_id = {c["name"].lower(): c["category_id"] for c in categories}
    return cat_name_to_id.get(category_name.lower()), cat_name_to_id

# -------------------------------
# UPDATE PRODUCT
# -------------------------------
def update_product(product_id, payload, access_token, org_id):
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": org_id,
        "Content-Type": "application/json"
    }
    url = f"https://commerce.zoho.com/store/api/v1/products/{product_id}?organization_id={org_id}"
    response = requests.put(url, headers=headers, json=payload)
    return response.status_code, response.text

# -------------------------------
# MAIN SCRIPT
# -------------------------------
def main():
    access_token = get_access_token()
    if not access_token:
        print("❌ Failed to get access token")
        return

    skus = get_sku_list()
    if not skus:
        print("❌ No SKUs to process. Exiting.")
        return

    # Choose processing mode
    mode = input(
        "\nChoose processing mode:\n"
        "1 - Apply same Category/Unit to all SKUs\n"
        "2 - Set Category/Unit individually per SKU\n"
        "Enter choice (1 or 2): "
    ).strip()

    log_rows = []

    if mode == "1":
        # Ask once for category and unit
        category_name = input("Enter Category (leave blank to skip): ").strip()
        unit = input("Enter Unit (leave blank to skip): ").strip()

        # Validate category once if provided
        cat_id, cat_map = (None, None)
        if category_name:
            cat_id, cat_map = get_category_id_from_name(access_token, org_id, category_name)
            while not cat_id:
                print(f"❌ Category '{category_name}' not found. Available categories: {list(cat_map.keys())}")
                category_name = input("Re-enter valid Category: ").strip()
                cat_id, cat_map = get_category_id_from_name(access_token, org_id, category_name)

        for sku in skus:
            print(f"\n🔍 Processing SKU: {sku}")
            product, parent_product = get_product_by_sku(sku, access_token, org_id)
            if not product:
                print(f"❌ SKU not found: {sku}")
                log_rows.append({"SKU": sku, "Status": "Not Found"})
                continue

            print(f"✅ Found product: {product.get('name')} (Parent: {parent_product.get('name') if parent_product else 'None'})")

            payload = {}
            if category_name:
                payload["category_id"] = cat_id
            if unit:
                payload["unit"] = unit

            target_product_id = parent_product["product_id"] if parent_product else product["product_id"]
            status_code, resp_text = update_product(target_product_id, payload, access_token, org_id)
            if status_code == 200:
                print(f"✅ Updated product '{product.get('name')}' | Category: '{category_name or 'Unchanged'}' | Unit: '{unit or 'Unchanged'}'")
                log_rows.append({"SKU": sku, "Status": "Updated", "Category": category_name or "Unchanged", "Unit": unit or "Unchanged"})
            else:
                print(f"❌ Failed to update '{product.get('name')}' | Category: '{category_name or 'Unchanged'}' | Unit: '{unit or 'Unchanged'}' : {status_code} {resp_text}")
                log_rows.append({"SKU": sku, "Status": "Failed", "Category": category_name or "Unchanged", "Unit": unit or "Unchanged"})

    elif mode == "2":
        for sku in skus:
            print(f"\n🔍 Processing SKU: {sku}")
            product, parent_product = get_product_by_sku(sku, access_token, org_id)
            if not product:
                print(f"❌ SKU not found: {sku}")
                log_rows.append({"SKU": sku, "Status": "Not Found"})
                continue

            print(f"✅ Found product: {product.get('name')} (Parent: {parent_product.get('name') if parent_product else 'None'})")

            # Prompt user for category/unit per SKU
            category_name = input("Enter Category (leave blank to skip): ").strip()
            unit = input("Enter Unit (leave blank to skip): ").strip()

            payload = {}
            if category_name:
                cat_id, cat_map = get_category_id_from_name(access_token, org_id, category_name)
                while not cat_id:
                    print(f"❌ Category '{category_name}' not found. Available categories: {list(cat_map.keys())}")
                    category_name = input("Re-enter valid Category: ").strip()
                    cat_id, cat_map = get_category_id_from_name(access_token, org_id, category_name)
                payload["category_id"] = cat_id
            if unit:
                payload["unit"] = unit

            target_product_id = parent_product["product_id"] if parent_product else product["product_id"]
            status_code, resp_text = update_product(target_product_id, payload, access_token, org_id)
            if status_code == 200:
                print(f"✅ Updated product '{product.get('name')}' | Category: '{category_name or 'Unchanged'}' | Unit: '{unit or 'Unchanged'}'")
                log_rows.append({"SKU": sku, "Status": "Updated", "Category": category_name or "Unchanged", "Unit": unit or "Unchanged"})
            else:
                print(f"❌ Failed to update '{product.get('name')}' | Category: '{category_name or 'Unchanged'}' | Unit: '{unit or 'Unchanged'}' : {status_code} {resp_text}")
                log_rows.append({"SKU": sku, "Status": "Failed", "Category": category_name or "Unchanged", "Unit": unit or "Unchanged"})

    else:
        print("❌ Invalid mode selected. Exiting.")
        return

    # Save log
    if log_rows:
        df_log = pd.DataFrame(log_rows)
        df_log.to_excel(LOG_FILE, index=False)
        print(f"\n📄 Log saved to {LOG_FILE}")




if __name__ == "__main__":
    main()
