import requests
import pandas as pd

# -------------------------------
# CONFIGURATION
# -------------------------------
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
LOG_FILE = "Update_Category_Brand_Unit_withSKURequest_Log.xlsx"
BASE_URL = "https://commerce.zoho.com/store/api/v1"
SESSION = requests.Session()


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
    resp = requests.post(url, params=params)
    data = resp.json()
    return data.get("access_token")


# -------------------------------
# SKU LIST
# -------------------------------
def get_sku_list():
    mode = input("Choose SKU input mode:\n1 - Generate SKUs\n2 - Provide SKU list (comma separated)\nEnter choice (1 or 2): ").strip()
    if mode == "1":
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (e.g. IP): ").strip()
        start = int(input("Enter start number (e.g. 1): ").strip())
        end = int(input("Enter end number (e.g. 10): ").strip())
        mid_code = item_name.upper()[:2]

        pad_option = input("Choose padding type:\n1 - Fixed 6-digit zero padding\n2 - No padding\n3 - Dynamic padding\nEnter choice (1, 2, or 3): ").strip()
        if pad_option == "1":
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(6)}" for num in range(start, end + 1)]
        elif pad_option == "2":
            skus = [f"{prefix}-{mid_code}-{num}" for num in range(start, end + 1)]
        elif pad_option == "3":
            pad_len = max(len(str(start)), len(str(end)))
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
        else:
            print("Invalid option. Exiting.")
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
# FETCH PRODUCT BY SKU
# -------------------------------
def get_product_by_sku(sku, access_token, org_id):
    sku = sku.strip().upper()
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}", "X-com-zoho-commerce-organizationid": org_id}
    resp = requests.get(f"{BASE_URL}/products?organization_id={org_id}&search_text={sku}", headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch products: {resp.status_code} {resp.text}")
        return None, None
    products = resp.json().get("products", [])
    for product in products:
        if str(product.get("sku", "")).strip().upper() == sku:
            return product, None
    for product in products:
        for variant in product.get("variants", []):
            if str(variant.get("sku", "")).strip().upper() == sku:
                return variant, product
    return None, None

# -------------------------------
# SELECT CATEGORY
# -------------------------------
def select_category(access_token, current_category=""):
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}",
               "X-com-zoho-commerce-organizationid": ORG_ID}
    resp = requests.get(f"{BASE_URL}/categories?organization_id={ORG_ID}", headers=headers)
    if resp.status_code != 200:
        print("⚠️ Failed to fetch categories. Skipping.")
        return current_category, None

    categories = resp.json().get("categories", [])
    cat_map = {c["name"].strip(): c["category_id"] for c in categories if "name" in c and "category_id" in c}
    cat_names = list(cat_map.keys())
    if not cat_names: return current_category, None

    print("\nAvailable categories:")
    for idx, c in enumerate(cat_names, 1):
        print(f"{idx}. {c}")

    while True:
        user_input = input(f"Category; Enter number or name from the list[{current_category}]: ").strip()
        if not user_input:
            return current_category, cat_map.get(current_category)

        # Check if input is a number in range
        if user_input.isdigit():
            idx = int(user_input)
            if 1 <= idx <= len(cat_names):
                selected_name = cat_names[idx-1]
                return selected_name, cat_map[selected_name]
            print("❌ Invalid number. Please select a valid number from the list.")
            continue

        # Check if input matches a category name (case insensitive)
        matches = [name for name in cat_names if name.lower() == user_input.lower()]
        if matches:
            return matches[0], cat_map[matches[0]]

        print("❌ Invalid input. Type a valid category name or number from the list.")



# -------------------------------
# SELECT BRAND
# SELECT BRAND
# -------------------------------
def select_brand(access_token, current_brand=""):
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}",
               "X-com-zoho-commerce-organizationid": ORG_ID}
    resp = requests.get(f"{BASE_URL}/brands?organization_id={ORG_ID}", headers=headers)
    if resp.status_code != 200:
        print("⚠️ Failed to fetch brands. Skipping.")
        return current_brand

    brands = resp.json().get("brands", [])
    brand_map = {b["name"].strip(): b["brand_id"] for b in brands if "name" in b and "brand_id" in b}
    brand_names = list(brand_map.keys())
    if not brand_names: return current_brand

    print("\nAvailable brands:")
    for idx, b in enumerate(brand_names, 1):
        print(f"{idx}. {b}")

    while True:
        user_input = input(f"Brand; Enter number or name from the list [{current_brand}]: ").strip()
        if not user_input:
            return current_brand

        # Check if input is a number in range
        if user_input.isdigit():
            idx = int(user_input)
            if 1 <= idx <= len(brand_names):
                return brand_names[idx-1]
            print("❌ Invalid number. Please select a valid number from the list.")
            continue

        # Check if input matches a brand name (case insensitive)
        matches = [name for name in brand_names if name.lower() == user_input.lower()]
        if matches:
            return matches[0]

        print("❌ Invalid input. Type a valid brand name or number from the list.")


# -------------------------------
# UPDATE PRODUCT
# -------------------------------
def update_product(product_id, payload, access_token, org_id):
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}",
               "X-com-zoho-commerce-organizationid": org_id,
               "Content-Type": "application/json"}
    resp = requests.put(f"{BASE_URL}/products/{product_id}?organization_id={org_id}", headers=headers, json=payload)
    return resp.status_code, resp.text

# MAIN SCRIPT
# -------------------------------
def main():
    access_token = get_access_token()
    if not access_token:
        print("❌ Failed to get access token")
        return

    while True:
        skus = get_sku_list()
        if not skus: break

        mode_choice = input(
            "\nChoose processing mode:\n"
            "1 - Apply same Category/Brand/Unit to all SKUs\n"
            "2 - Set Category/Brand/Unit individually per SKU\n"
            "Enter choice (1 or 2): ").strip()
        log_rows = []

        if mode_choice == "1":
            category_name, category_id = select_category(access_token)
            brand = select_brand(access_token)
            unit = input("Enter Unit (leave blank to skip): ").strip()
            for sku in skus:
                print(f"\n🔍 Processing SKU: {sku}")
                product, parent_product = get_product_by_sku(sku, access_token, ORG_ID)
                if not product:
                    print(f"❌ SKU not found: {sku}")
                    log_rows.append({"SKU": sku, "Status": "Not Found"})
                    continue

                payload = {}
                if category_id: payload["category_id"] = category_id
                if brand: payload["brand"] = brand
                if unit: payload["unit"] = unit

                target_id = parent_product["product_id"] if parent_product else product["product_id"]
                status_code, resp_text = update_product(target_id, payload, access_token, ORG_ID)
                status = "Updated" if status_code == 200 else "Failed"

                log_rows.append({
                    "SKU": sku,
                    "Status": status,
                    "Category": category_name or "Unchanged",
                    "Brand": brand or "Unchanged",
                    "Unit": unit or "Unchanged"
                })

                # Detailed console output
                print(f"{'✅' if status_code==200 else '❌'} SKU: {sku} | Name: {product.get('name')}")
                print(f"    → Category: {category_name or 'Unchanged'} | Brand: {brand or 'Unchanged'} | Unit: {unit or 'Unchanged'}")

        elif mode_choice == "2":
            for sku in skus:
                print(f"\n🔍 Processing SKU: {sku}")
                product, parent_product = get_product_by_sku(sku, access_token, ORG_ID)
                if not product:
                    print(f"❌ SKU not found: {sku}")
                    log_rows.append({"SKU": sku, "Status": "Not Found"})
                    continue

                category_name, category_id = select_category(access_token)
                brand = select_brand(access_token)
                unit = input("Enter Unit (leave blank to skip): ").strip()

                payload = {}
                if category_id: payload["category_id"] = category_id
                if brand: payload["brand"] = brand
                if unit: payload["unit"] = unit

                target_id = parent_product["product_id"] if parent_product else product["product_id"]
                status_code, resp_text = update_product(target_id, payload, access_token, ORG_ID)
                status = "Updated" if status_code == 200 else "Failed"

                log_rows.append({
                    "SKU": sku,
                    "Status": status,
                    "Category": category_name or "Unchanged",
                    "Brand": brand or "Unchanged",
                    "Unit": unit or "Unchanged"
                })

                # Detailed console output
                print(f"{'✅' if status_code==200 else '❌'} SKU: {sku} | Name: {product.get('name')}")
                print(f"    → Category: {category_name or 'Unchanged'} | Brand: {brand or 'Unchanged'} | Unit: {unit or 'Unchanged'}")

        else:
            print("❌ Invalid mode. Skipping this batch.")
            continue

        if log_rows:
            df_log = pd.DataFrame(log_rows)
            df_log.to_excel(LOG_FILE, index=False)
            print(f"\n📄 Log saved to {LOG_FILE}")

        again = input("\nDo you want to perform another update? (y/n): ").strip().lower()
        if again != "y":
            print("Exiting...")
            break

if __name__ == "__main__":
    main()
