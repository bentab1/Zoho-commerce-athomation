import requests
from datetime import datetime
import pandas as pd

# Config
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
LOG_FILE = "AdjustStockViaCommerce_Worked-Log.xlsx"

def get_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print("✅ Access token obtained.")
        return token
    else:
        print(f"❌ Failed to get access token: {response.status_code} {response.text}")
        return None

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
        return mode, skus

    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
        print(f"Using provided SKUs: {skus}")
        return mode, skus
    else:
        print("Invalid mode. Exiting.")
        exit()


def fetch_products(access_token):
    print("Fetching products from Zoho Commerce...")
    products = []
    page = 1
    per_page = 100  # max per Zoho API docs

    while True:
        url = f"https://commerce.zoho.com/store/api/v1/products?page={page}&per_page={per_page}&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if resp.status_code != 200 or "products" not in data:
            print("❌ Error fetching products:", data)
            return []
        products.extend(data["products"])
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    print(f"✅ Fetched {len(products)} products.")
    return products
def perform_inventory_adjustment(access_token, reason, line_items):
    url = f"https://commerce.zoho.com/store/api/v1/inventoryadjustments?organization_id={ORG_ID}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "adjustment_type": "quantity",
        "reason": reason,
        "line_items": line_items
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in (200, 201):
        print(f"✅ Inventory adjustment successful.")
        return True
    else:
        print(f"❌ Inventory adjustment failed: {response.status_code} - {response.text}")
        return False

def main():
    access_token = get_access_token()
    if not access_token:
        return

    sku_mode, skus = get_sku_list()  # <-- unpack here

    reason = input("Enter reason for stock adjustment: ").strip()
    if not reason:
        print("Reason is required. Exiting.")
        return

    adjust_mode = input("Choose adjustment mode:\n1 - One adjustment value for all SKUs\n2 - Enter adjustment per SKU\nEnter choice (1 or 2): ").strip()
    if adjust_mode not in ["1", "2"]:
        print("Invalid mode. Exiting.")
        return

    products = fetch_products(access_token)
    if not products:
        print("No products fetched, exiting.")
        return

    sku_map = {}
    for product in products:
        product_id = product.get("product_id")
        product_name = product.get("name", "Unknown")
        for variant in product.get("variants", []):
            sku = variant.get("sku", "").upper()
            variant_id = variant.get("variant_id")
            stock_on_hand = variant.get("stock_on_hand", 0)
            if sku and variant_id:
                sku_map[sku] = (product_id, variant_id, stock_on_hand, product_name)

    logs = []

    if adjust_mode == "1":
        try:
            adjustment = int(input("Enter stock adjustment quantity for all SKUs (use negative to reduce): ").strip())
        except ValueError:
            print("Invalid adjustment quantity, must be an integer.")
            return

        for sku in skus:
            if sku in sku_map:
                product_id, variant_id, current_stock, product_name = sku_map[sku]
                new_stock = current_stock + adjustment
                if new_stock < 0:
                    new_stock = 0

                line_items = [{"item_id": variant_id, "quantity_adjusted": adjustment}]
                success = perform_inventory_adjustment(access_token, reason, line_items)

                status = "Success" if success else "API update failed"
                if success:
                    print(f"✅ Updated stock_on_hand to {new_stock} for variant {variant_id} of product {product_id}")
                print(f"SKU: {sku} | Item ID: {variant_id} | Item Name: {product_name} | Qty Adjusted: {adjustment} | New Stock: {new_stock} | Status: {status}")

                logs.append({
                    "Item ID": variant_id,
                    "SKU": sku,
                    "Item Name": product_name,
                    "Quantity Adjusted": adjustment,
                    "New Stock": new_stock,
                    "Status": status,
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                print(f"SKU: {sku} | Status: SKU not found")
                logs.append({
                    "Item ID": None,
                    "SKU": sku,
                    "Item Name": None,
                    "Quantity Adjusted": None,
                    "New Stock": None,
                    "Status": "SKU not found",
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

    else:  # adjust_mode == "2"
        for sku in skus:
            if sku in sku_map:
                try:
                    adjustment = int(input(f"Enter stock adjustment quantity for SKU {sku} (use negative to reduce): ").strip())
                except ValueError:
                    print(f"Invalid adjustment for SKU {sku}, skipping.")
                    continue

                product_id, variant_id, current_stock, product_name = sku_map[sku]
                new_stock = current_stock + adjustment
                if new_stock < 0:
                    new_stock = 0

                line_items = [{"item_id": variant_id, "quantity_adjusted": adjustment}]
                success = perform_inventory_adjustment(access_token, reason, line_items)

                status = "Success" if success else "API update failed"
                if success:
                    print(f"✅ Updated stock_on_hand to {new_stock} for variant {variant_id} of product {product_id}")
                print(f"SKU: {sku} | Item ID: {variant_id} | Item Name: {product_name} | Qty Adjusted: {adjustment} | New Stock: {new_stock} | Status: {status}")

                logs.append({
                    "Item ID": variant_id,
                    "SKU": sku,
                    "Item Name": product_name,
                    "Quantity Adjusted": adjustment,
                    "New Stock": new_stock,
                    "Status": status,
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                print(f"SKU: {sku} | Status: SKU not found")
                logs.append({
                    "Item ID": None,
                    "SKU": sku,
                    "Item Name": None,
                    "Quantity Adjusted": None,
                    "New Stock": None,
                    "Status": "SKU not found",
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

    # Save logs to Excel
    df_logs = pd.DataFrame(logs)
    df_logs.to_excel(LOG_FILE, index=False)
    print(f"✅ Logged adjustment results to {LOG_FILE}")

if __name__ == "__main__":
    main()
