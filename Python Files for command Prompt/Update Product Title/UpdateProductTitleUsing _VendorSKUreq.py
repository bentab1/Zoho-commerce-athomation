import requests
from datetime import datetime
import pandas as pd

# ===================
# CONFIGURATION
# ===================
ORG_ID = "891730368"

# Commerce API
ZOHO_COM_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_COM_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_COM_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
API_BASE_URL = "https://commerce.zoho.com/store/api/v1"

# Inventory API
ZOHO_INV_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_INV_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"

LOG_FILE = "Commerce_WeightUpdate_Log.xlsx"

# ===================
# TOKEN FUNCTIONS
# ===================
def get_zoho_commerce_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    payload = {
        "refresh_token": ZOHO_COM_REFRESH_TOKEN,
        "client_id": ZOHO_COM_CLIENT_ID,
        "client_secret": ZOHO_COM_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, data=payload).json()
    if "access_token" in resp:
        print("✅ Got Commerce token")
        return resp["access_token"]
    else:
        raise Exception(f"❌ Failed to get Commerce access token: {resp}")

def get_zoho_inventory_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_INV_REFRESH_TOKEN,
        "client_id": ZOHO_INV_CLIENT_ID,
        "client_secret": ZOHO_INV_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, params=params)
    if resp.status_code == 200:
        print("✅ Got Inventory token")
        return resp.json().get("access_token")
    else:
        print(f"❌ Failed to get Inventory token: {resp.status_code} {resp.text}")
        return None

# ===================
# FETCH VENDORS
# ===================
def fetch_all_vendors(inv_token):
    vendors = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/contacts?page={page}&per_page=200&type=vendor&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
        resp = requests.get(url, headers=headers).json()
        if "contacts" not in resp:
            print("❌ Error fetching vendors:", resp)
            return []
        vendors.extend([v for v in resp["contacts"] if v.get("contact_type") == "vendor"])
        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return vendors

# ===================
# SELECT PRODUCTS BY VENDOR (Your Function)
# ===================
def select_products_by_vendor():
    inv_token = get_zoho_inventory_token()
    if not inv_token:
        return []

    vendors = fetch_all_vendors(inv_token)
    if not vendors:
        print("❌ No vendors found.")
        return []

    print("\nAvailable Vendors:")
    for i, v in enumerate(vendors, 1):
        print(f"{i}. {v.get('contact_name')} (ID: {v.get('contact_id')})")

    choice = input("\nSelect vendor (number or vendor ID): ").strip()
    vendor_id = None
    if choice.isdigit() and 1 <= int(choice) <= len(vendors):
        vendor_id = vendors[int(choice) - 1].get("contact_id")
    else:
        for v in vendors:
            if v.get("contact_id") == choice:
                vendor_id = choice
                break
    if not vendor_id:
        print("❌ Invalid vendor selection.")
        return []

    vendor_items = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/items?vendor_id={vendor_id}&organization_id={ORG_ID}&page={page}&per_page=200"
        headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
        resp = requests.get(url, headers=headers).json()
        if "items" not in resp:
            print("❌ Error fetching items:", resp)
            return []

        for item in resp["items"]:
            sku = item.get("sku", "").upper()
            name = item.get("name", "")
            vendor_items.append({"sku": sku, "name": name})

        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1

    print("\nInventory Items for Selected Vendor:")
    for idx, item in enumerate(vendor_items, 1):
        print(f"{idx}. {item['name']} (SKU: {item['sku']})")

    selected_numbers = input("\nSelect SKU numbers (comma separated, e.g. 1,3,5 or 'all'): ").strip()
    if selected_numbers.lower() == "all":
        return [item["sku"] for item in vendor_items]

    selected_skus = []
    for num in selected_numbers.split(","):
        num = num.strip()
        if num.isdigit():
            idx = int(num) - 1
            if 0 <= idx < len(vendor_items):
                selected_skus.append(vendor_items[idx]["sku"])
    print(f"\nSelected SKUs: {selected_skus}")
    return selected_skus

# ===================
# FETCH COMMERCE PARENT PRODUCTS
# ===================
def fetch_commerce_parent_products_for_skus(com_token, skus):
    products = []
    page = 1
    while True:
        url = f"{API_BASE_URL}/products?page={page}&per_page=200&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {com_token}"}
        resp = requests.get(url, headers=headers).json()
        if "products" not in resp:
            print("❌ Error fetching Commerce products:", resp)
            return []
        for p in resp["products"]:
            if not p.get("parent_product_id") and p.get("sku", "").upper() in skus:
                products.append({
                    "id": p.get("product_id"),
                    "name": p.get("name"),
                    "sku": p.get("sku", "").upper(),
                    "weight": p.get("weight", 0),
                    "status": p.get("status")
                })
        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return products

# ===================
# UPDATE PRODUCT WEIGHT
# ===================
def update_commerce_product_weight(com_token, product_id, weight):
    url = f"{API_BASE_URL}/products/{product_id}?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {com_token}", "Content-Type": "application/json"}
    payload = {"weight": weight}
    resp = requests.put(url, headers=headers, json=payload)
    return resp.status_code == 200

# ===================
# LOG RESULTS
# ===================
def log_results(logs):
    df = pd.DataFrame(logs)
    df.to_excel(LOG_FILE, index=False)
    print(f"\n📄 Log saved to {LOG_FILE}")

# ===================
# MAIN WORKFLOW
# ===================
def main():
    com_token = get_zoho_commerce_token()
    selected_skus = select_products_by_vendor()
    if not selected_skus:
        print("❌ No SKUs selected.")
        return

    products = fetch_commerce_parent_products_for_skus(com_token, selected_skus)
    if not products:
        print("❌ No parent products found in Commerce for selected SKUs.")
        return

    print("\nAvailable Commerce Parent Products:")
    for idx, p in enumerate(products, 1):
        print(f"{idx}. {p['name']} (SKU: {p['sku']}, Current Weight: {p['weight']})")

    choice = input("\nSelect products (comma-separated numbers, or 'all'): ").strip().lower()
    if choice == "all":
        selected_products = products
    else:
        selected_products = []
        for num in choice.split(","):
            num = num.strip()
            if num.isdigit():
                idx = int(num) - 1
                if 0 <= idx < len(products):
                    selected_products.append(products[idx])

    try:
        new_weight = float(input("Enter new weight (kg): ").strip())
    except ValueError:
        print("❌ Invalid weight value.")
        return

    logs = []
    for p in selected_products:
        success = update_commerce_product_weight(com_token, p["id"], new_weight)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "✅ Success" if success else "❌ Failed"
        print(f"{status} | {p['name']} (SKU: {p['sku']}) → New Weight: {new_weight}")
        logs.append({
            "timestamp": timestamp,
            "sku": p["sku"],
            "product_name": p["name"],
            "status": status,
            "weight": new_weight
        })

    log_results(logs)
    print("\n✅ Update process finished.")

if __name__ == "__main__":
    main()
