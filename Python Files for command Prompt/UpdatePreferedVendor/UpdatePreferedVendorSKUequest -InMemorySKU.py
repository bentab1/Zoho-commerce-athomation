import requests
from openpyxl import Workbook
from datetime import datetime

# Configuration
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = 891730368

def get_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, params=params)
    if resp.status_code == 200:
        print("✅ Access token obtained.")
        return resp.json().get("access_token")
    else:
        print(f"❌ Failed to get access token: {resp.status_code} {resp.text}")
        return None

# === FETCH ITEMS ===
def fetch_all_items(access_token):
    items = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/items?page={page}&per_page=200&organization_id={ORG_ID}"
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

# === FETCH VENDORS ===
def fetch_all_vendors(access_token):
    vendors = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/contacts?page={page}&per_page=200&type=vendor&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if "contacts" not in data:
            print("❌ Error fetching vendors:", data)
            return []
        vendors.extend([v for v in data["contacts"] if v.get("contact_type") == "vendor"])
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return vendors

# === GET SKU LIST ===
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
        return mode, skus

    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
        return mode, skus
    else:
        print("Invalid mode. Exiting.")
        exit()

# === SELECT VENDOR FROM LIST ===
def select_vendor_from_list(vendors):
    print("\nAvailable Vendors:")
    for idx, v in enumerate(vendors, start=1):
        print(f"{idx}: {v.get('contact_name')} (ID: {v.get('contact_id')})")

    choice = input("Enter vendor number to select: ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(vendors):
        print("Invalid choice. Exiting.")
        exit()
    vendor = vendors[int(choice) - 1]
    return {"vendor_id": vendor.get("contact_id"), "vendor_display_name": vendor.get("contact_name")}

# === GET VENDOR FOR SKU(S) ===
def get_preferred_vendor_for_skus(skus, vendors):
    mode = input("\nChoose vendor mode:\n1 - One vendor per SKU\n2 - One vendor for all SKUs\nEnter choice (1 or 2): ").strip()
    vendor_data = {}
    if mode == "1":
        for sku in skus:
            print(f"\nSKU: {sku}")
            vendor_data[sku] = select_vendor_from_list(vendors)
    elif mode == "2":
        print("\nSelect vendor for all SKUs:")
        selected_vendor = select_vendor_from_list(vendors)
        for sku in skus:
            vendor_data[sku] = selected_vendor
    else:
        print("Invalid mode. Exiting.")
        exit()
    return vendor_data

# === UPDATE ITEM ===
def update_item_vendor(access_token, item_id, vendor_id, vendor_display_name):
    url = f"https://inventory.zoho.com/api/v1/items/{item_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "vendor_id": vendor_id,
        "vendor_name": vendor_display_name
    }
    resp = requests.put(url, json=payload, headers=headers, params={"organization_id": ORG_ID})
    try:
        data = resp.json()
    except:
        return False, f"Invalid JSON response: {resp.text}"

    if resp.status_code == 200 and data.get("code") == 0:
        return True, "Vendor updated successfully."
    else:
        return False, f"HTTP {resp.status_code} - {data.get('message', 'Unknown error')}"

# === MAIN ===
# === MAIN ===
def main():
    access_token = get_access_token()
    if not access_token:
        return

    sku_mode, skus = get_sku_list()
    vendors = fetch_all_vendors(access_token)
    if not vendors:
        print("❌ No vendors found.")
        return

    user_pref_vendors = get_preferred_vendor_for_skus(skus, vendors)
    items = fetch_all_items(access_token)
    sku_to_item = {item.get("sku", "").upper(): item for item in items}

    wb = Workbook()
    ws = wb.active
    ws.title = "Vendor Update Log"
    ws.append(["Timestamp", "SKU", "Item Name", "Preferred Vendor ID", "Preferred Vendor Display Name", "Update Status"])

    not_found_skus = []  # Track SKUs not in inventory

    for sku in skus:
        item = sku_to_item.get(sku)
        if not item:
            not_found_skus.append(sku)
            ws.append([datetime.now(), sku, "Not Found", "", "", "SKU not found"])
            continue

        user_vendor = user_pref_vendors.get(sku)
        if not user_vendor:
            ws.append([datetime.now(), sku, item.get("name"), "", "", "No preferred vendor provided"])
            continue

        success, message = update_item_vendor(
            access_token,
            item["item_id"],
            user_vendor["vendor_id"],
            user_vendor["vendor_display_name"]
        )

        ws.append([
            datetime.now(),
            sku,
            item.get("name"),
            user_vendor["vendor_id"],
            user_vendor["vendor_display_name"],
            "Success" if success else f"Failed: {message}"
        ])

    log_filename = "UpdatePreferredVendorSKU_Log.xlsx"
    wb.save(log_filename)
    print(f"\n✅ Update log saved to {log_filename}")

    # ✅ Success message with vendor name(s)
    unique_vendors = {v["vendor_display_name"] for v in user_pref_vendors.values() if v}
    if len(unique_vendors) == 1:
        print(f"✅ All SKUs Found have been updated with the preferred vendor: {list(unique_vendors)[0]}")
    else:
        print("✅ All SKUs Found have been updated with their selected preferred vendors.")

    # --- Prompt to repeat ---
    while True:
        again = input("\nDo you want to update another preferred vendor? (y/n): ").strip().lower()
        if again == "y":
            main()
            break
        elif again == "n":
            print("Exiting... Goodbye!")
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")




if __name__ == "__main__":
    main()

