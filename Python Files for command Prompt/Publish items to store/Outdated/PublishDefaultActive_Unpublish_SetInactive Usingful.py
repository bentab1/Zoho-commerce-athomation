import requests

# ===================
# CONFIGURATION
# ===================

# Commerce API
ZOHO_COM_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_COM_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_COM_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
API_BASE_URL = "https://commerce.zoho.com/store/api/v1"

# Inventory API
ZOHO_INV_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_INV_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = "891730368"

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
    resp = requests.post(url, data=payload)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    else:
        raise Exception(f"❌ Failed to get Commerce access token: {data}")

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
# COMMERCE FUNCTIONS
# ===================

def fetch_all_products(token, page=1, per_page=50):
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-com-zoho-store-organizationid": ORG_ID
    }
    url = f"{API_BASE_URL}/products?page={page}&per_page={per_page}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("products", []), data.get("page_context", {})

def update_product_visibility(token, product_id, show_flag=None, variant_id=None, active_flag=None):
    """
    Update publish (show_in_storefront) and active status (status field) for a product/variant.
    """
    url = f"{API_BASE_URL}/products/{product_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-com-zoho-store-organizationid": ORG_ID,
        "Content-Type": "application/json"
    }

    payload = {}

    # Handle publish/unpublish
    if show_flag is not None:
        payload["show_in_storefront"] = show_flag
        # Automatically set status to active when publishing if not explicitly overridden
        if show_flag and active_flag is None:
            payload["status"] = "active"

    # Handle active/inactive explicitly
    if active_flag is not None:
        payload["status"] = "active" if active_flag else "inactive"

    # Include variant_id if updating a variant
    if variant_id:
        payload["variant_id"] = variant_id

    # Abort if payload would be empty
    if not payload:
        print("❌ Nothing to update, request payload would be empty.")
        return False

    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code == 200:
        action = "published" if show_flag else "unpublished" if show_flag == False else "activated" if active_flag else "deactivated"
        print(f"✅ {action} successfully: Product ID {product_id} Variant ID {variant_id if variant_id else 'no variant'}")
        return True
    else:
        print(f"❌ Error: {resp.status_code} - {resp.text}")
        return False


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
        return True
    else:
        print(f"❌ Failed to delete vendor {vendor_id}: {resp.status_code} {resp.text}")
        return False

def select_products_by_vendor():
    inv_token = get_zoho_inventory_token()
    if not inv_token:
        print("❌ Cannot fetch vendors without Inventory token.")
        return []
    
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
        return []

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

    # Fetch inventory items
    vendor_items = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/items?vendor_id={vendor_id}&organization_id={ORG_ID}&page={page}&per_page=200"
        headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if "items" not in data:
            print("❌ Error fetching items for vendor:", data)
            return []
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
        return []

    print("\nInventory Items for Selected Vendor:")
    for idx, item in enumerate(vendor_items, 1):
        print(f"{idx}. {item['name']} (SKU: {item['sku']})")

    chosen_skus = [item["sku"] for item in vendor_items]
    return chosen_skus

# ===================
# MAP INVENTORY SKUS TO COMMERCE PRODUCTS
# ===================

def map_inventory_to_commerce(sku_list, com_token):
    parent_map = {}
    full_product_map = {}
    page = 1
    while True:
        products, page_context = fetch_all_products(com_token, page=page, per_page=50)
        if not products:
            break
        for prod in products:
            parent_id = prod.get('product_id')
            parent_name = prod.get('name')
            variants = prod.get('variants', [])
            full_product_map[parent_id] = {"name": parent_name, "variants": []}

            if variants:
                for var in variants:
                    var_sku = var.get('sku', '').upper()
                    full_product_map[parent_id]["variants"].append({
                        "sku": var_sku,
                        "variant_id": var.get('variant_id'),
                        "name": var.get('name')
                    })
                    parent_map[var_sku] = {
                        "parent_id": parent_id,
                        "parent_name": parent_name,
                        "variant_id": var.get('variant_id'),
                        "variant_name": var.get('name')
                    }
            else:
                prod_sku = prod.get('sku', '').upper()
                full_product_map[parent_id]["variants"].append({
                    "sku": prod_sku,
                    "variant_id": None,
                    "name": parent_name
                })
                parent_map[prod_sku] = {
                    "parent_id": parent_id,
                    "parent_name": parent_name,
                    "variant_id": None,
                    "variant_name": None
                }
        if not page_context.get("has_more_page"):
            break
        page += 1

    matched_parents = {}
    for sku in sku_list:
        if sku in parent_map:
            pid = parent_map[sku]["parent_id"]
            matched_parents[pid] = full_product_map[pid]
    return matched_parents

# ===================
# PUBLISH / ACTIVE / INACTIVE
# ===================

def publish_selected_products(sku_list, show_flag=None, active_flag=None):
    com_token = get_zoho_commerce_token()
    parents = map_inventory_to_commerce(sku_list, com_token)
    if not parents:
        print("❌ No matching commerce products found for selected SKUs.")
        return

    print("\nCommerce Products for Selected SKUs:")
    for idx, (pid, pdata) in enumerate(parents.items(), 1):
        print(f"{idx}. {pdata['name']} (Parent)")
        for vidx, var in enumerate(pdata['variants'], 1):
            print(f"   {vidx}. {var['name']} (SKU: {var['sku']})")

    choice = input(
        "\nChoose parent or variant numbers to update "
        "(e.g., 1,2 or 1.1,1.2 for variants, 'all' for all): "
    ).strip()

    to_update = []

    if choice.lower() == 'all':
        for pid, pdata in parents.items():
            for var in pdata['variants']:
                to_update.append((pid, var['variant_id'], var['sku'], pdata['name'], var['name']))
    else:
        selections = choice.split(',')
        for sel in selections:
            parts = sel.strip().split('.')
            try:
                parent_idx = int(parts[0]) - 1
                parent_key = list(parents.keys())[parent_idx]
                pdata = parents[parent_key]

                if len(parts) == 2:
                    var_idx = int(parts[1]) - 1
                    var = pdata['variants'][var_idx]
                    to_update.append((parent_key, var['variant_id'], var['sku'], pdata['name'], var['name']))
                else:
                    for var in pdata['variants']:
                        to_update.append((parent_key, var['variant_id'], var['sku'], pdata['name'], var['name']))
            except Exception as e:
                print(f"❌ Invalid selection {sel}: {e}")

    # Update products
    for pid, vid, sku, pname, vname in to_update:
        success = update_product_visibility(com_token, pid, show_flag, vid, active_flag)
        if success:
            action = "published" if show_flag else "unpublished" if show_flag == False else "activated" if active_flag else "deactivated"
            variant_text = f"(variant {vid})" if vid else "(no variant)"
            print(f"✅ {action} successfully: {pname} {variant_text} SKU: {sku} ID: {pid}")
        else:
            variant_text = f"(variant {vid})" if vid else "(no variant)"
            print(f"❌ Failed: {pname} {variant_text} SKU: {sku} ID: {pid}")


# ===================
# MAIN
# ===================

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

# def main():
#     print("Choose input mode:\n1 - Fetch by Vendor\n2 - Generate SKUs")
#     mode = input("Enter choice: ").strip()

#     if mode == '1':
#         sku_list = select_products_by_vendor()
#     elif mode in ['2']:
#         _, sku_list = get_sku_list()  # Reuse your existing SKU function
#     else:
#         print("Invalid mode. Exiting.")
#         return

#     if not sku_list:
#         print("No SKUs selected. Exiting.")
#         return

#     print("\nChoose action:\n1 - Publish (Active by default)\n2 - Unpublish\n3 - Set Active/Inactive only")
#     while True:
#         choice = input("Enter choice (1, 2, or 3): ").strip()
#         if choice == '1':
#             show_flag = True
#             active_flag = None
#             break
#         elif choice == '2':
#             show_flag = False
#             active_flag = None
#             break
#         elif choice == '3':
#             show_flag = None
#             af_choice = input("Set product Active? (y/n): ").strip().lower()
#             active_flag = True if af_choice == 'y' else False
#             break
#         else:
#             print("Invalid choice. Please enter 1, 2, or 3.")

#     publish_selected_products(sku_list, show_flag, active_flag)


# if __name__ == '__main__':
#     main()
def main():
    while True:
        print("Choose input mode:\n1 - Fetch by Vendor\n2 - Provide SKU list (comma separated)\n3 - Generate SKUs")
        mode = input("Enter choice: ").strip()

        if mode == '1':
            sku_list = select_products_by_vendor()
        elif mode == '2':
            sku_raw = input("Enter SKUs separated by commas: ").strip()
            sku_list = [sku.strip().upper() for sku in sku_raw.split(',') if sku.strip()]
        elif mode == '3':
            prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
            item_name = input("Enter item name (e.g. IP): ").strip()
            start = int(input("Enter start number (e.g. 1): ").strip())
            end = int(input("Enter end number (e.g. 10): ").strip())
            pad_len = int(input("Enter padding length (e.g. 6): ").strip())
            mid_code = item_name.upper()[:2]
            sku_list = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end+1)]
            print(f"Generated SKUs: {sku_list}")
        else:
            print("Invalid mode. Exiting.")
            return

        if not sku_list:
            print("No SKUs selected. Exiting.")
            return

        print("\nChoose action:\n1 - Publish (Active by default)\n2 - Unpublish\n3 - Set Active/Inactive only")
        while True:
            choice = input("Enter choice (1, 2, or 3): ").strip()
            if choice == '1':
                show_flag = True
                active_flag = None
                break
            elif choice == '2':
                show_flag = False
                active_flag = None
                break
            elif choice == '3':
                show_flag = None
                af_choice = input("Set product Active? (y/n): ").strip().lower()
                active_flag = True if af_choice == 'y' else False
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

        publish_selected_products(sku_list, show_flag, active_flag)

        # Ask user if they want to continue
        again = input("\nDo you want to perform another action? (y/n): ").strip().lower()
        if again != 'y':
            print("Exiting program.")
            break


if __name__ == '__main__':
    main()


