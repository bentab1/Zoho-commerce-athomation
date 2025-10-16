import requests
from openpyxl import Workbook
from datetime import datetime

# Configuration - replace with your real credentials
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
        url = f"https://inventory.zoho.com/api/v1/vendors?page={page}&per_page=200&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if "contacts" not in data:
            print("❌ Error fetching vendors:", data)
            return []
        vendors.extend(data["contacts"])
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

# === GET VENDOR FOR SKU(S) ===
def get_preferred_vendor_for_skus(skus):
    mode = input("\nChoose preferred vendor input mode:\n1 - One vendor per SKU\n2 - One vendor for all SKUs\nEnter choice (1 or 2): ").strip()
    vendor_data = {}
    if mode == "1":
        for sku in skus:
            print(f"\nSKU: {sku}")
            vendor_id = input("  Preferred Vendor ID: ").strip()
            vendor_display_name = input("  Preferred Vendor Display Name: ").strip()
            if vendor_id and vendor_display_name:
                vendor_data[sku] = {"vendor_id": vendor_id, "vendor_display_name": vendor_display_name}
            else:
                vendor_data[sku] = None
    elif mode == "2":
        vendor_id = input("Enter Preferred Vendor ID for all SKUs: ").strip()
        vendor_display_name = input("Enter Preferred Vendor Display Name for all SKUs: ").strip()
        for sku in skus:
            vendor_data[sku] = {"vendor_id": vendor_id, "vendor_display_name": vendor_display_name} if vendor_id and vendor_display_name else None
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
        "vendor_name": vendor_display_name  # Zoho expects vendor_name in JSON
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
def main():
    access_token = get_access_token()
    if not access_token:
        return

    sku_mode, skus = get_sku_list()
    user_pref_vendors = get_preferred_vendor_for_skus(skus)

    items = fetch_all_items(access_token)
    vendors = fetch_all_vendors(access_token)
    vendor_lookup = {v.get("contact_id"): v.get("contact_name") for v in vendors}
    sku_to_item = {item.get("sku", "").upper(): item for item in items}

    wb = Workbook()
    ws = wb.active
    ws.title = "Vendor Update Log"
    ws.append(["Timestamp", "SKU", "Item Name", "Preferred Vendor ID", "Preferred Vendor Display Name", "Update Status"])

    for sku in skus:
        item = sku_to_item.get(sku)
        if not item:
            print(f"❌ SKU {sku} not found in inventory.")
            ws.append([datetime.now(), sku, "Not Found", "", "", "SKU not found"])
            continue

        user_vendor = user_pref_vendors.get(sku)
        if not user_vendor:
            print(f"⚠️ No preferred vendor provided for SKU {sku}, skipping.")
            ws.append([datetime.now(), sku, item.get("name"), "", "", "No preferred vendor provided"])
            continue

        print(f"🔄 Updating SKU: {sku} → Vendor: {user_vendor['vendor_display_name']} ({user_vendor['vendor_id']})")
        success, message = update_item_vendor(
            access_token,
            item["item_id"],
            user_vendor["vendor_id"],
            user_vendor["vendor_display_name"]
        )
        print(f"   Status: {message}")

        ws.append([
            datetime.now(),
            sku,
            item.get("name"),
            user_vendor["vendor_id"],
            user_vendor["vendor_display_name"],
            "Success" if success else f"Failed: {message}"
        ])

    log_filename = "UpdatePreferedVendorSKURequest_Log2.xlsx"
    wb.save(log_filename)
    print(f"\n✅ Update log saved to {log_filename}")

if __name__ == "__main__":
    main()
