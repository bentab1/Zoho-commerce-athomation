import requests
import csv
from datetime import datetime

# ===================
# CONFIGURATION
# ===================
LOG_FILE = "VendorItems_Returnable_Log.csv"
ZOHO_INV_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_INV_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = "891730368"
BASE_URL = "https://inventory.zoho.com/api/v1"

# ===================
# TOKEN FUNCTION
# ===================
def get_inventory_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_INV_REFRESH_TOKEN,
        "client_id": ZOHO_INV_CLIENT_ID,
        "client_secret": ZOHO_INV_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, params=params)
    if resp.status_code == 200:
        print("✅ Access token obtained.")
        return resp.json().get("access_token")
    else:
        print(f"❌ Failed to get access token: {resp.status_code} {resp.text}")
        return None

# ===================
# FETCH VENDORS
# ===================
def fetch_all_vendors(token):
    vendors = []
    page = 1
    while True:
        url = f"{BASE_URL}/contacts?page={page}&per_page=200&type=vendor&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
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
# FETCH VENDOR ITEMS
# ===================
def fetch_vendor_items(token, vendor_id):
    items = []
    page = 1
    while True:
        url = f"{BASE_URL}/items?vendor_id={vendor_id}&organization_id={ORG_ID}&page={page}&per_page=200"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        resp = requests.get(url, headers=headers).json()
        if "items" not in resp:
            print("❌ Error fetching items:", resp)
            return []
        for i in resp["items"]:
            items.append({
                "sku": i.get("sku", "").upper(),
                "name": i.get("name", ""),
                "item_id": i.get("item_id"),
                "variants": i.get("item_variants", [])
            })
        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return items

# ===================
# UPDATE ITEM RETURNABLE
# ===================
def update_item_returnable(token, item_id, returnable=True):
    url = f"{BASE_URL}/items/{item_id}?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}
    payload = {"is_returnable": returnable}
    resp = requests.put(url, headers=headers, json=payload)
    return resp.status_code == 200

# ===================
# LOGGING FUNCTION
# ===================
def log_results(logs):
    keys = ["timestamp", "sku", "item_name", "status"]
    with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for entry in logs:
            writer.writerow(entry)

# ===================
# USER INTERACTION
# ===================
def select_vendor(token):
    vendors = fetch_all_vendors(token)
    if not vendors:
        print("❌ No vendors found.")
        return None
    print("\nAvailable Vendors:")
    for i, v in enumerate(vendors, 1):
        print(f"{i}. {v.get('contact_name')} (ID: {v.get('contact_id')})")
    while True:
        choice = input("Select vendor (number or ID): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(vendors):
            return vendors[int(choice)-1]["contact_id"]
        for v in vendors:
            if v.get("contact_id") == choice:
                return choice
        print("❌ Invalid selection. Try again.")

def select_items(items):
    print("\nVendor Inventory Items:")
    for idx, item in enumerate(items, 1):
        print(f"{idx}. {item['name']} (SKU: {item['sku']})")
    while True:
        choice = input("Select items (comma-separated numbers, or 'all'): ").strip().lower()
        if choice == "all":
            return items
        selected = []
        try:
            indexes = [int(x.strip()) for x in choice.split(",")]
            for i in indexes:
                if 1 <= i <= len(items):
                    selected.append(items[i-1])
            if selected:
                return selected
        except:
            pass
        print("❌ Invalid selection. Try again.")

def ask_returnable():
    while True:
        choice = input("Mark selected items as returnable? (y/n): ").strip().lower()
        if choice in ["y", "yes"]:
            return True
        elif choice in ["n", "no", ""]:
            return False
        print("❌ Enter 'y' or 'n'.")

# ===================
# MAIN SCRIPT
# ===================
def fetch_all_items(token):
    """Fetch all inventory items (not vendor-specific)."""
    items = []
    page = 1
    while True:
        url = f"{BASE_URL}/items?organization_id={ORG_ID}&page={page}&per_page=200"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        resp = requests.get(url, headers=headers).json()
        if "items" not in resp:
            print("❌ Error fetching all items:", resp)
            return []
        for i in resp["items"]:
            items.append({
                "sku": i.get("sku", "").upper(),
                "name": i.get("name", ""),
                "item_id": i.get("item_id"),
                "variants": i.get("item_variants", [])
            })
        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return items


from getpass import getpass  # for hidden password input

def main():
    token = get_inventory_token()
    if not token:
        return

    logs = []

    while True:
        print("\n====================")
        print("  Inventory Update Menu")
        print("====================")
        print("1. Set ALL inventory items returnable/non-returnable (Admin Only)")
        print("2. Set items by vendor")
        print("3. Exit")
        choice = input("Choose an option (1/2/3): ").strip()

        if choice == "1":
            # --- ADMIN PASSWORD CHECK ---
            password = getpass("🔑 Enter admin password: ").strip()
            if password != "Admin123":  # Case-sensitive
                print("❌ Incorrect password. Returning to menu.")
                continue

            # --- ALL INVENTORY FLOW ---
            all_items = fetch_all_items(token)
            if not all_items:
                print("❌ No inventory items found.")
                continue

            returnable = ask_returnable()  # True or False explicitly

            print("\n🔄 Updating all inventory items...")
            for idx, item in enumerate(all_items, start=1):
                success = update_item_returnable(token, item["item_id"], returnable)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                status = "✅ Success" if success else "❌ Failed"
                print(f"{idx}. {status} | {item['name']} (SKU: {item['sku']}) | Returnable: {returnable}")
                logs.append({"timestamp": timestamp, "sku": item["sku"], "item_name": item["name"], "status": status})

            log_results(logs)
            print("\n✅ All inventory items processed and logged.")

        elif choice == "2":
            # --- VENDOR-SPECIFIC FLOW (existing) ---
            vendor_id = select_vendor(token)
            if not vendor_id:
                return

            items = fetch_vendor_items(token, vendor_id)
            if not items:
                print("❌ No items for this vendor.")
                continue

            selected_items = select_items(items)
            returnable = ask_returnable()

            print("\n🔄 Updating vendor items...")
            for idx, item in enumerate(selected_items, start=1):
                success = update_item_returnable(token, item["item_id"], returnable)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                status = "✅ Success" if success else "❌ Failed"
                print(f"{idx}. {status} | {item['name']} (SKU: {item['sku']}) | Returnable: {returnable}")
                logs.append({"timestamp": timestamp, "sku": item["sku"], "item_name": item["name"], "status": status})

            log_results(logs)
            print("\n✅ Vendor items processed and logged.")

        elif choice == "3":
            print("👋 Exiting...")
            break
        else:
            print("❌ Invalid option. Try again.")

        again = input("\nDo you want to perform another update? (y/n): ").strip().lower()
        if again != "y":
            break


if __name__ == "__main__":
    main()
