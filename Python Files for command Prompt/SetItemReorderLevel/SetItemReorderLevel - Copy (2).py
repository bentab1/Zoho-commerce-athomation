import requests
import json
import csv
import os

# =========================
# CONFIG
# =========================
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = 891730368
LOG_FILE = "Update_ReorderLevel_log.csv"

# =========================
# AUTH FUNCTIONS
# =========================
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

# =========================
# INVENTORY FUNCTIONS
# =========================
def fetch_inventory_items(access_token, vendor_id=None):
    items = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/items?organization_id={ORG_ID}&page={page}&per_page=200"
        if vendor_id:
            url += f"&vendor_id={vendor_id}"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if "items" not in data:
            print("❌ Error fetching items:", data)
            return []
        items.extend(data["items"])
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return items

def update_reorder_level(access_token, item_id, reorder_level, item_name, sku):
    url = f"https://inventory.zoho.com/api/v1/items/{item_id}?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}", "Content-Type": "application/json"}
    payload = {"reorder_level": reorder_level}
    response = requests.put(url, headers=headers, json=payload)
    try:
        resp_json = response.json()
    except Exception as e:
        return False, f"❌ JSON parse error for {item_name} ({sku}): {e}"

    if response.status_code == 200 and resp_json.get("code") == 0:
        msg = f"✅ Updated reorder level {reorder_level} for {item_name} (SKU: {sku})"
        print(msg)
        return True, msg
    else:
        msg = f"❌ Failed {item_name} (SKU: {sku}): {resp_json.get('message', response.text)}"
        print(msg)
        return False, msg

# =========================
# VENDOR FUNCTIONS
# =========================
def fetch_all_vendors(access_token):
    vendors = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/contacts?page={page}&per_page=200&type=vendor&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if "contacts" not in data:
            return []
        vendors.extend([v for v in data["contacts"] if v.get("contact_type") == "vendor"])
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return vendors

def select_vendor(access_token):
    vendors = fetch_all_vendors(access_token)
    if not vendors:
        print("❌ No vendors found.")
        return None

    print("\nAvailable Vendors:")
    for i, v in enumerate(vendors, 1):
        print(f"{i}. {v['contact_name']} (ID: {v['contact_id']})")

    choice = input("Select vendor (number or ID): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(vendors):
        return vendors[int(choice)-1]['contact_id']
    for v in vendors:
        if v["contact_id"] == choice:
            return choice
    return None

# =========================
# SKU FUNCTIONS
# =========================
def get_sku_list():
    mode = input("Choose SKU input mode:\n1 - Generate SKUs\n2 - Provide SKU list (comma separated)\nEnter choice (1 or 2): ").strip()
    if mode == "1":
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (e.g. IP): ").strip()
        try:
            start = int(input("Enter start number (e.g. 1): ").strip())
            end = int(input("Enter end number (e.g. 10): ").strip())
        except ValueError:
            print("❌ Start and End must be integers.")
            return mode, []

        if end < start:
            print("❌ End number must be greater than or equal to start number.")
            return mode, []

        mid_code = item_name.upper()[:2]

        pad_option = input("Choose padding type:\n1 - Fixed 6-digit zero padding (e.g. 000065)\n2 - No padding (e.g. 563)\n3 - Dynamic padding based on input\nEnter choice (1, 2, or 3): ").strip()

        if pad_option == "1":
            pad_len = 6
        elif pad_option == "2":
            pad_len = 0
        elif pad_option == "3":
            pad_len = max(len(str(start)), len(str(end)))
        else:
            print("❌ Invalid padding option.")
            return mode, []

        skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len) if pad_len>0 else str(num)}" for num in range(start, end+1)]
        print(f"Generated SKUs: {skus}")
        return mode, skus

    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
        print(f"Using provided SKUs: {skus}")
        return mode, skus
    else:
        print("❌ Invalid mode.")
        return mode, []

# =========================
# LOGGING
# =========================
def log_to_csv(log_rows):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["item_id","item_name","sku","reorder_level","status"])
        writer.writerows(log_rows)

# =========================
# MAIN
# =========================
def main():
    access_token = get_access_token()
    if not access_token:
        return

    print("\nChoose Mode:")
    print("1 - Set Reorder Level by Vendor")
    print("2 - Set Reorder Level by SKU")
    print("3 - Set Reorder Level for ALL Products (Admin Only)")
    mode = input("Enter mode (1/2/3): ").strip()

    try:
        reorder_level = int(input("Enter reorder level: ").strip())
    except ValueError:
        print("❌ Must be an integer.")
        return

    items = []

    if mode == "1":  # Vendor
        vendor_id = select_vendor(access_token)
        if not vendor_id:
            print("❌ Invalid vendor.")
            return
        items = fetch_inventory_items(access_token, vendor_id)

    elif mode == "2":  # SKU
        _, skus = get_sku_list()   # unpack tuple (mode, skus)
        all_items = fetch_inventory_items(access_token)
        sku_map = {i.get("sku","").upper(): i for i in all_items}
        items = []
        for s in skus:
            if s in sku_map:
                items.append(sku_map[s])
            else:
                print(f"⚠️ SKU {s} not found in inventory.")  # warn missing SKUs

    elif mode == "3":  # All Products (admin)
        pwd = input("Enter Admin Password: ").strip()
        if pwd != "Admin123":
            print("❌ Wrong password.")
            return
        items = fetch_inventory_items(access_token)

    else:
        print("❌ Invalid mode.")
        return

    logs = []
    for item in items:
        item_id = item.get("item_id")
        sku = item.get("sku","").upper()
        name = item.get("name","Unknown")
        success, msg = update_reorder_level(access_token, item_id, reorder_level, name, sku)
        logs.append([item_id, name, sku, reorder_level, "Updated" if success else "Failed"])

    log_to_csv(logs)
    print(f"✅ Results logged to {LOG_FILE}")

# =========================
# RUN LOOP
# =========================
if __name__ == "__main__":
    while True:
        main()
        again = input("\nDo you want to perform another update? (y/n): ").strip().lower()
        if again != "y":
            print("👋 Exiting. Goodbye!")
            break
