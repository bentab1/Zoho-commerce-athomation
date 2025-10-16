import requests

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
ZOHO_INV_CLIENT_ID = ZOHO_COM_CLIENT_ID
ZOHO_INV_CLIENT_SECRET = ZOHO_COM_CLIENT_SECRET
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"

# ===================
# TOKEN FUNCTIONS
# ===================
def get_token(refresh_token, client_id, client_secret):
    url = "https://accounts.zoho.com/oauth/v2/token"
    payload = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }
    resp = requests.post(url, data=payload)
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"❌ Failed to get token: {resp.status_code} {resp.text}")
    return data["access_token"]

def get_zoho_commerce_token():
    return get_token(ZOHO_COM_REFRESH_TOKEN, ZOHO_COM_CLIENT_ID, ZOHO_COM_CLIENT_SECRET)

def get_zoho_inventory_token():
    return get_token(ZOHO_INV_REFRESH_TOKEN, ZOHO_INV_CLIENT_ID, ZOHO_INV_CLIENT_SECRET)

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
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if "items" not in data:
            print("❌ Error fetching items:", data)
            return []

        for item in data["items"]:
            sku = item.get("sku", "").upper()
            name = item.get("name", "")
            vendor_items.append({"sku": sku, "name": name})

        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1

    print("\nInventory Items for Selected Vendor:")
    for idx, item in enumerate(vendor_items, 1):
        print(f"{idx}. {item['name']} (SKU: {item['sku']})")

    return [item["sku"] for item in vendor_items]

def get_sku_list_manual_or_generated():
    mode = input("Choose SKU input mode:\n1 - Generate SKUs\n2 - Provide SKU list (comma separated)\nEnter choice (1 or 2): ").strip()
    if mode == "1":
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (e.g. IP): ").strip()
        start = int(input("Enter start number (e.g. 1): ").strip())
        end = int(input("Enter end number (e.g. 10): ").strip())
        mid_code = item_name.upper()[:2]

        pad_option = input("Choose padding type:\n1 - Fixed 6-digit zero padding\n2 - No padding\n3 - Dynamic padding\nEnter choice: ").strip()
        if pad_option == "1":
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(6)}" for num in range(start, end + 1)]
        elif pad_option == "2":
            skus = [f"{prefix}-{mid_code}-{num}" for num in range(start, end + 1)]
        elif pad_option == "3":
            pad_len = max(len(str(start)), len(str(end)))
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
        else:
            print("Invalid padding option. Exiting.")
            exit()
        return skus
    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        return [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
    else:
        print("Invalid mode. Exiting.")
        exit()

# ===================
# ATTRIBUTE FUNCTIONS
# ===================
def get_existing_attributes(com_token):
    url = f"{API_BASE_URL}/attributes"
    headers = {"Authorization": f"Zoho-oauthtoken {com_token}", "X-com-zoho-store-organizationid": ORG_ID}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("attributes", [])

def create_attribute(com_token, attribute_name, choices):
    url = f"{API_BASE_URL}/attributes"
    headers = {"Authorization": f"Zoho-oauthtoken {com_token}", "X-com-zoho-store-organizationid": ORG_ID}
    payload = {"attribute_name": attribute_name, "choices": [{"choice_name": c} for c in choices]}
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def fetch_product_id_by_sku(com_token, sku):
    url = f"{API_BASE_URL}/products?sku={sku}"
    headers = {"Authorization": f"Zoho-oauthtoken {com_token}", "X-com-zoho-store-organizationid": ORG_ID}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    products = resp.json().get("products", [])
    if not products:
        print(f"❌ SKU not found: {sku}")
        return None
    return products[0]["product_id"]

def update_product_attribute(com_token, product_id, attribute_id, choices):
    url = f"{API_BASE_URL}/products/{product_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {com_token}",
        "X-com-zoho-store-organizationid": ORG_ID
    }
    payload = {"attributes": [{"attribute_id": attribute_id, "attribute_option_name": c} for c in choices]}
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in [200, 201]:
        print(f"✅ Updated product {product_id} with attribute choices: {choices}")
    else:
        print(f"❌ Failed to update product {product_id}: {resp.status_code} {resp.text}")


# ===================
# ALWAYS CREATE ATTRIBUTE
# ===================
def sync_attribute(com_token, attribute_name, choices):
    # Sanitize choices: strip and remove empty strings
    choices = [c.strip() for c in choices if c.strip()]

    if not choices:
        raise ValueError("❌ No valid choices provided for the attribute.")

    print(f"Creating attribute '{attribute_name}' with choices {choices}...")
    attr_resp = create_attribute(com_token, attribute_name, choices)
    return attr_resp["attribute"]["attribute_id"]


# ===================
# PRODUCT UPDATE
# ===================
def apply_attribute_to_products(com_token, skus, attribute_name, choices, mode):
    attribute_id = sync_attribute(com_token, attribute_name, choices)

    for sku in skus:
        if mode == "2":  # confirm one by one
            confirm = input(f"Apply {attribute_name}:{choices} to SKU {sku}? (y/n): ").strip().lower()
            if confirm != "y":
                continue

        product_id = fetch_product_id_by_sku(com_token, sku)
        if not product_id:
            continue
        update_product_attribute(com_token, product_id, attribute_id, choices)

# ===================
# MAIN
# ===================
def main():
    com_token = get_zoho_commerce_token()

    mode = input("\nChoose mode:\n1 - Vendor flow\n2 - SKU flow\nEnter choice (1 or 2): ").strip()
    if mode == "1":
        skus = select_products_by_vendor()
    elif mode == "2":
        skus = get_sku_list_manual_or_generated()
    else:
        print("Invalid mode.")
        return

    if not skus:
        print("❌ No SKUs found.")
        return

    attribute_name = input("Enter attribute name (e.g. Color): ").strip()
    choices = input("Enter choices separated by commas (e.g. Red, Blue, Green): ").split(",")
    choices = [c.strip() for c in choices if c.strip()]

    apply_mode = input("Apply mode:\n1 - Apply to all selected products\n2 - Apply one by one\nEnter choice: ").strip()
    apply_attribute_to_products(com_token, skus, attribute_name, choices, apply_mode)

if __name__ == "__main__":
    main()
