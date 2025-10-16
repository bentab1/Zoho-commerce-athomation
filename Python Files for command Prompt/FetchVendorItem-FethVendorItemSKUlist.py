import requests

# ===================
# CONFIGURATION
# ===================

# Inventory API
ZOHO_INV_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_INV_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = "891730368"

# ===================
# TOKEN FUNCTIONS
# ===================

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
        print("✅ Inventory access token obtained.")
        return resp.json().get("access_token")
    else:
        print(f"❌ Failed to get Inventory access token: {resp.status_code} {resp.text}")
        return None

# ===================
# INVENTORY FUNCTIONS
# ===================

def fetch_all_vendors(inv_token):
    vendors = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/contacts?page={page}&per_page=200&type=vendor&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
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

def delete_vendor(inv_token, vendor_id):
    url = f"https://inventory.zoho.com/api/v1/contacts/{vendor_id}"
    headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
    resp = requests.delete(url, headers=headers, params={"organization_id": ORG_ID})
    if resp.status_code == 200:
        print(f"✅ Vendor {vendor_id} deleted successfully.")
    else:
        print(f"❌ Failed to delete vendor {vendor_id}: {resp.status_code} {resp.text}")

def select_products_by_vendor():
    inv_token = get_zoho_inventory_token()
    if not inv_token:
        print("❌ Cannot fetch vendors without Inventory token.")
        return []

    while True:
        vendors = fetch_all_vendors(inv_token)
        if not vendors:
            print("❌ No vendors found.")
            return []

        print("\nAvailable Vendors:")
        for i, v in enumerate(vendors, 1):
            print(f"{i}. {v.get('contact_name')} (ID: {v.get('contact_id')})")

        choice = input("\nSelect vendor (number or vendor ID) or type 'delete' to remove a vendor: ").strip()
        if choice.lower() == 'delete':
            del_choice = input("Enter vendor number or ID to delete: ").strip()
            del_vendor_id = None
            if del_choice.isdigit() and 1 <= int(del_choice) <= len(vendors):
                del_vendor_id = vendors[int(del_choice) - 1].get('contact_id')
            else:
                del_vendor_id = del_choice
            if del_vendor_id:
                delete_vendor(inv_token, del_vendor_id)
            continue

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
            continue

        # Fetch vendor items
        vendor_items = []
        page = 1
        while True:
            url = f"https://inventory.zoho.com/api/v1/items?vendor_id={vendor_id}&organization_id={ORG_ID}&page={page}&per_page=200"
            headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
            resp = requests.get(url, headers=headers)
            data = resp.json()
            if "items" not in data:
                print("❌ Error fetching items for vendor:", data)
                vendor_items = []
                break
            for item in data["items"]:
                vendor_items.append({
                    "sku": item.get("sku","").upper(),
                    "name": item.get("name","")
                })
            if not data.get("page_context", {}).get("has_more_page", False):
                break
            page += 1

        if not vendor_items:
            print("❌ No inventory items found for selected vendor.")
            continue

        # Show inventory items
        print("\nInventory Items for Selected Vendor:")
        for idx, item in enumerate(vendor_items, 1):
            print(f"{idx}. {item['name']} (SKU: {item['sku']})")

        # # Show sorted SKUs
        # sorted_skus = sorted([item["sku"] for item in vendor_items])
        # print("\nSorted SKU List:")
        # for sku in sorted_skus:
        #             print(sku)
        # Show sorted SKUs as comma-separated list
        sorted_skus = sorted([item["sku"] for item in vendor_items])
        print("\n📦 Generated SKUs:")
        group_size = 5
        for i in range(0, len(sorted_skus), group_size):
            print(", ".join(sorted_skus[i:i+group_size]))


        # Exit immediately if user does not want to select another vendor
        again = input("\nDo you want to select another vendor? (y/n): ").strip().lower()
        if again != 'y':
            return sorted_skus

# ===================
# MAIN
# ===================

def main():
    # Call vendor selection
    sku_list = select_products_by_vendor()
    
    # If user chose not to select any vendor, exit silently
    if not sku_list:
        return  # Simply exit

if __name__ == "__main__":
    main()
