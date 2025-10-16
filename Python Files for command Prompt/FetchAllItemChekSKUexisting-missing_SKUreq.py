import requests
import pandas as pd

# === Zoho OAuth & Org ===
CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = "891730368"

# === Get Access Token ===
def get_access_token():
    print("🔐 Fetching access token...")
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    res = requests.post(url, params=params)
    res.raise_for_status()
    token = res.json()["access_token"]
    print("✅ Access token received.\n")
    return token

# === Get SKU List from User ===
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

# === Fetch item by SKU ===
def fetch_item_by_sku(access_token, org_id, sku):
    url = f"https://inventory.zoho.com/api/v1/items?organization_id={org_id}&sku={sku}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        return data.get("items", [])[0] if data.get("items") else None
    return None

# === Fetch All Inventory Items ===
def fetch_all_inventory_items(access_token, org_id):
    print("📦 Fetching all items in inventory...")
    all_items = []
    page = 1
    per_page = 200
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    while True:
        url = f"https://inventory.zoho.com/api/v1/items?organization_id={org_id}&page={page}&per_page={per_page}"
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            break
        data = res.json()
        items = data.get("items", [])
        if not items:
            break
        all_items.extend(items)
        if len(items) < per_page:
            break
        page += 1

    print(f"✅ Total items in inventory: {len(all_items)}\n")
    return all_items

# === Main Function ===
def check_skus():
    print("🚀 Starting SKU check...")
    token = get_access_token()

    # Fetch all inventory items
    all_items = fetch_all_inventory_items(token, ORG_ID)
    all_items_log = []
    for item in all_items:
        all_items_log.append({
            "Item ID": item.get("item_id", ""),
            "Item Name": item.get("name", ""),
            "SKU": item.get("sku", ""),
            "Status": item.get("status", ""),
            "Available Stock": item.get("available_stock", ""),
            "Rate": item.get("rate", "")
        })

    all_items_path = "All_Items_List.xlsx"
    pd.DataFrame(all_items_log).to_excel(all_items_path, index=False)
    print(f"📦 All inventory items saved to: {all_items_path}\n")

    # Get SKUs from user (generated or manual)
    skus = get_sku_list()
    total = len(skus)
    print(f"🔍 Checking {total} SKUs...\n")

    existing = []
    missing = []

    for idx, sku in enumerate(skus, 1):
        print(f"🔎 [{idx}/{total}] Checking SKU: {sku}")
        item = fetch_item_by_sku(token, ORG_ID, sku)
        if item:
            print(f"   ✅ Found: {item['name']}")
            existing.append({
                "SKU": sku,
                "Item Name": item["name"],
                "Item ID": item["item_id"]
            })
        else:
            print(f"   ❌ Not Found in Inventory")
            missing.append({"Missing SKU": sku})

    # Save matched/unmatched SKUs
    exist_path = "Existing_SKUs.xlsx"
    missing_path = "Missing_SKUs.xlsx"

    pd.DataFrame(existing).to_excel(exist_path, index=False)
    pd.DataFrame(missing).to_excel(missing_path, index=False)

    print("\n✅ Finished checking specified SKUs.")
    print(f"📄 Existing SKUs saved to: {exist_path}")
    print(f"📄 Missing SKUs saved to: {missing_path}")

    return exist_path, missing_path, all_items_path

# === Entry Point ===
if __name__ == "__main__":
    check_skus()
