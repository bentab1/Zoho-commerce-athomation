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

LOG_FILE = "StockAdjustmentLog.xlsx"

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
        return resp.json().get("access_token")
    else:
        print(f"❌ Failed to get Inventory access token: {resp.status_code} {resp.text}")
        return None

# ===================
# VENDOR & SKU FUNCTIONS
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
        vendor_id = vendors[int(choice)-1].get("contact_id")
    else:
        for v in vendors:
            if v.get("contact_id") == choice:
                vendor_id = choice
                break
    if not vendor_id:
        print("❌ Invalid vendor selection.")
        return []

    # Fetch vendor items
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
            sku = item.get("sku","").upper()
            name = item.get("name","")
            available_stock = get_current_stock(inv_token, sku)
            vendor_items.append({
                "sku": sku,
                "name": name,
                "available_stock": available_stock if available_stock is not None else "Unknown"
            })

        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1

    # Display items with stock
    print("\nInventory Items for Selected Vendor:")
    for idx, item in enumerate(vendor_items, 1):
        print(f"{idx}. {item['name']} (SKU: {item['sku']}): Available stock: {item['available_stock']}")

    return [item["sku"] for item in vendor_items]

import requests

def get_inventory_item_name(inv_token, sku):
    """
    Fetch the actual item name from Zoho Inventory using SKU.
    Returns the item name as string if found, else None.
    """
    url = f"https://inventory.zoho.com/api/v1/items?sku={sku}&organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code in (200, 201):
            data = resp.json()
            items = data.get("items", [])
            if items:
                return items[0].get("name")
        return None
    except Exception as e:
        print(f"❌ Error fetching name for SKU {sku}: {e}")
        return None

def get_sku_list(inv_token):
    """
    Get SKUs either by providing a list manually or generating them.
    Shows current stock with numbering and actual item name from inventory.
    """
    mode = input(
        "Choose SKU input mode:\n"
        "1 - Enter SKUs separated by commas\n"
        "2 - Generate SKUs\n"
        "Enter choice (1 or 2): "
    ).strip()

    if mode == "1":
        # --- Provide SKU list manually ---
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]

    elif mode == "2":
        # --- Generate SKUs ---
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (used only for code generation): ").strip()
        start = int(input("Enter start number (e.g. 1): ").strip())
        end = int(input("Enter end number (e.g. 10): ").strip())
        mid_code = item_name.upper()[:2]

        pad_option = input(
            "Choose padding type:\n"
            "1 - Fixed 6-digit zero padding\n"
            "2 - No padding\n"
            "3 - Dynamic padding\n"
            "Enter choice (1, 2, or 3): "
        ).strip()

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

    else:
        print("Invalid mode. Exiting.")
        exit()

    # 🔹 Show SKUs with actual inventory item names and current stock
    print("\n📦 SKUs with current stock:")
    for idx, sku in enumerate(skus, 1):
        stock = get_current_stock(inv_token, sku)
        actual_name = get_inventory_item_name(inv_token, sku)
        stock_display = stock if stock is not None else "SKU not found in the inventory"
        icon = "✅" if stock is not None else "❌"
        name_display = actual_name if actual_name else "Unknown Item"
        print(f"{icon} {idx}. {name_display} [{sku}]: Available stock = {stock_display}")

    return skus


# ===================
# COMMERCE FUNCTIONS
# ===================
def fetch_all_products(token, page=1, per_page=50):
    headers = {"Authorization": f"Zoho-oauthtoken {token}","X-com-zoho-store-organizationid": ORG_ID}
    url = f"{API_BASE_URL}/products?page={page}&per_page={per_page}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("products", []), data.get("page_context", {})

def map_inventory_to_commerce(sku_list, com_token):
    parent_map = {}
    full_map = {}
    page = 1
    while True:
        products, page_context = fetch_all_products(com_token, page)
        if not products: break
        for prod in products:
            pid = prod.get('product_id')
            pname = prod.get('name')
            variants = prod.get('variants', [])
            full_map[pid] = {"name": pname, "variants": []}
            if variants:
                for var in variants:
                    sku = var.get('sku','').upper()
                    full_map[pid]["variants"].append({"sku":sku,"variant_id":var.get('variant_id'),"name":var.get('name')})
                    parent_map[sku] = {"parent_id": pid, "variant_id": var.get('variant_id')}
            else:
                sku = prod.get('sku','').upper()
                full_map[pid]["variants"].append({"sku":sku,"variant_id":None,"name":pname})
                parent_map[sku] = {"parent_id": pid, "variant_id": None}
        if not page_context.get("has_more_page"): break
        page += 1
    matched = {}
    for sku in sku_list:
        if sku in parent_map:
            pid = parent_map[sku]["parent_id"]
            matched[pid] = full_map[pid]
    return matched


def perform_stock_adjustment(com_token, parent_map, inv_token):
    """
    Perform stock adjustment for SKUs once.
    Returns True if user wants to go back to main menu, False otherwise.
    """

    # --- Select mode ---
    print("\nStock Adjustment Mode:\n1 - Add/Subtract Stock\n2 - Set Stock Level")
    choice = input("Enter choice (1 or 2) or 'exit': ").strip()
    if choice.lower() == "exit":
        print("⏹️ Stock adjustment stopped by user.")
        return False

    if choice not in ["1", "2"]:
        print("❌ Invalid choice.")
        return False
    mode = "add" if choice == "1" else "set_level"

    # --- Enter reason ---
    reason = input("Enter reason for stock adjustment or 'exit': ").strip()
    if reason.lower() == "exit":
        print("⏹️ Stock adjustment stopped by user.")
        return False
    if not reason:
        print("❌ Reason required. Exiting.")
        return False

    # --- Quantity entry mode ---
    print("\nQuantity Entry Mode:\n1 - One quantity for all SKUs\n2 - Enter quantity per SKU")
    qty_mode = input("Enter choice (1 or 2) or 'exit': ").strip()
    if qty_mode.lower() == "exit" or qty_mode not in ["1", "2"]:
        print("❌ Invalid choice. Exiting.")
        return False

    # --- Prepare SKU list ---
    sku_list = []
    for pid, pdata in parent_map.items():
        for var in pdata["variants"]:
            sku_list.append((pid, var["variant_id"], var["sku"], pdata["name"], var["name"]))

    # --- Single quantity for all SKUs ---
    if qty_mode == "1":
        try:
            qty_input = int(input("Enter stock quantity or adjustment for all SKUs: ").strip())
        except ValueError:
            print("❌ Invalid number. Exiting.")
            return False

        for pid, vid, sku, pname, vname in sku_list:
            adjust_stock(com_token, pid, vid, sku, pname, vname, qty_input, mode, reason, inv_token)

    # --- Per SKU ---
    else:
        for idx, (pid, vid, sku, pname, vname) in enumerate(sku_list, 1):
            current_stock = get_current_stock(inv_token, sku)
            if current_stock is None:
                print(f"{idx}. {pname} ({vname}) [{sku}]: ❌ Could not fetch current stock. Skipping.")
                continue

            try:
                qty_input = input(
                    f"{idx}. {pname} ({vname}) [{sku}] (Current stock: {current_stock}) - "
                    f"Enter desired adjustment/stock level or 'exit': "
                ).strip()
                if qty_input.lower() == "exit":
                    print("⏹️ Stock adjustment stopped by user.")
                    return False
                qty_input = int(qty_input)
            except ValueError:
                print(f"❌ Invalid quantity for {pname} ({vname}) [{sku}]. Skipping.")
                continue

            adjust_stock(com_token, pid, vid, sku, pname, vname, qty_input, mode, reason, inv_token)

    return False



def get_current_stock(inv_token, sku):
    """Fetch current stock for a SKU from Inventory API."""
    url_item = f"https://inventory.zoho.com/api/v1/items?sku={sku}&organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
    try:
        resp = requests.get(url_item, headers=headers)
        data = resp.json()
        if "items" not in data or not data["items"]:
            return None
        return float(data["items"][0].get("available_stock", 0))
    except:
        return None

def get_default_warehouse(inv_token):
    """Fetch the default warehouse_id from Zoho Inventory."""
    url = f"https://inventory.zoho.com/api/v1/warehouses?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch warehouses: {resp.status_code}")
        return None
    data = resp.json()
    warehouses = data.get("warehouses", [])
    if not warehouses:
        print("❌ No warehouses found.")
        return None
    # Return the first warehouse as default
    return warehouses[0]["warehouse_id"]


def get_sku_list(inv_token):
    """
    Generate SKUs and show current stock with numbering and actual item name from inventory.
    """
    prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
    item_name = input("Enter item name (used only for code generation): ").strip()
    start = int(input("Enter start number (e.g. 1): ").strip())
    end = int(input("Enter end number (e.g. 10): ").strip())
    mid_code = item_name.upper()[:2]

    pad_option = input(
        "Choose padding type:\n1 - Fixed 6-digit zero padding\n2 - No padding\n3 - Dynamic padding\nEnter choice (1, 2, or 3): "
    ).strip()

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

    # 🔹 Show generated SKUs with actual inventory item names
    print("\n📦 Generated SKUs with current stock:")
    for idx, sku in enumerate(skus, 1):
        stock = get_current_stock(inv_token, sku)
        actual_name = get_inventory_item_name(inv_token, sku)  # fetch item name from inventory
        stock_display = stock if stock is not None else "SKU not found in the inventory"
        icon = "✅" if stock is not None else "❌"
        name_display = actual_name if actual_name else "Unknown Item"
        print(f"{icon} {idx}. {name_display} [{sku}]: Available stock = {stock_display}")

    return skus


# def get_sku_list(inv_token):
#     """
#     Generate SKUs and show current stock with numbering and actual item name from inventory.
#     """
#     prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
#     item_name = input("Enter item name (used only for code generation): ").strip()
#     start = int(input("Enter start number (e.g. 1): ").strip())
#     end = int(input("Enter end number (e.g. 10): ").strip())
#     mid_code = item_name.upper()[:2]

#     pad_option = input(
#         "Choose padding type:\n1 - Fixed 6-digit zero padding\n2 - No padding\n3 - Dynamic padding\nEnter choice (1, 2, or 3): "
#     ).strip()

#     if pad_option == "1":
#         pad_len = 6
#         skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
#     elif pad_option == "2":
#         skus = [f"{prefix}-{mid_code}-{str(num)}" for num in range(start, end + 1)]
#     elif pad_option == "3":
#         pad_len = max(len(str(start)), len(str(end)))
#         skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
#     else:
#         print("Invalid padding option. Exiting.")
#         exit()

#     # 🔹 Show generated SKUs with actual inventory item names
#     print("\n📦 Generated SKUs with current stock:")
#     for idx, sku in enumerate(skus, 1):
#         stock = get_current_stock(inv_token, sku)
#         actual_name = get_inventory_item_name(inv_token, sku)  # fetch item name from inventory
#         stock_display = stock if stock is not None else "SKU not found in the inventory"
#         icon = "✅" if stock is not None else "❌"
#         name_display = actual_name if actual_name else "Unknown Item"
#         print(f"{icon} {idx}. {name_display} [{sku}]: Available stock = {stock_display}")

#     return skus


def get_sku_list(inv_token):
    mode = input(
        "Choose SKU input mode:\n"
        "1 - Generate SKUs\n"
        "2 - Provide SKU list (comma separated)\n"
        "Enter choice (1 or 2): "
    ).strip()

    skus = []  # ensure a flat list

    if mode == "1":
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (e.g. IP): ").strip()
        start = int(input("Enter start number (e.g. 1): ").strip())
        end = int(input("Enter end number (e.g. 10): ").strip())
        mid_code = item_name.upper()[:2]

        pad_option = input(
            "Choose padding type:\n"
            "1 - Fixed 6-digit zero padding (e.g. 000065)\n"
            "2 - No padding (e.g. 563)\n"
            "3 - Dynamic padding based on input\n"
            "Enter choice (1, 2, or 3): "
        ).strip()

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

    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]

    else:
        print("Invalid mode. Exiting.")
        exit()

    # 🔹 Show SKUs with actual inventory item names and current stock
    print("\n📦 SKUs with current stock:")
    for idx, sku in enumerate(skus, 1):
        stock = get_current_stock(inv_token, sku)
        actual_name = get_inventory_item_name(inv_token, sku)  # fetch item name from inventory
        stock_display = stock if stock is not None else "SKU not found in the inventory"
        icon = "✅" if stock is not None else "❌"
        name_display = actual_name if actual_name else "Unknown Item"
        print(f"{icon} {idx}. {name_display} [{sku}]: Available stock = {stock_display}")

    return mode, skus


def adjust_stock(com_token, pid, vid, sku, pname, vname, desired_level, mode, reason, inv_token, index=None):
    """
    Adjust stock for a SKU with numbering and success/failure icon, using actual item name from inventory.
    """
    # Fetch current stock
    current_stock = get_current_stock(inv_token, sku)
    # Get actual item name from inventory, fallback to pname if not found
    actual_name = get_inventory_item_name(inv_token, sku) or pname  
    idx_display = f"{index}." if index is not None else ""
    # Handle case where stock cannot be fetched
    if current_stock is None:
        print(f"❌ {index}. {actual_name} [{sku}]: Could not fetch current stock.")
        return

    # Calculate adjustment quantity
    if mode == "add":
        quantity = desired_level
    elif mode == "set_level":
        quantity = desired_level - current_stock
    else:
        print(f"❌ {actual_name} [{sku}]: Invalid mode")
        return

    # Prepare API request
    url = f"{API_BASE_URL}/inventoryadjustments?organization_id={ORG_ID}"
    payload = {
        "adjustment_type": "quantity",
        "reason": reason,
        "line_items": [{"item_id": vid, "quantity_adjusted": quantity}],
    }
    headers = {
        "Authorization": f"Zoho-oauthtoken {com_token}",
        "Content-Type": "application/json"
    }

    # Execute stock adjustment
    resp = requests.post(url, headers=headers, json=payload)

    # Determine status icon and text
    if resp.status_code in (200, 201):
        status_icon = "✅"
        status_text = "Success"
    else:
        status_icon = "❌"
        status_text = f"Failed: {resp.status_code}"
#  # Display output
#     print(
#         f"{status_icon} {index}. {actual_name} ({vname}) [{sku}]: {status_text} "
#         f"(Adjusted by {quantity}, Current: {current_stock}, Target: {desired_level})"
#     )
    print(
        f"{status_icon}[{sku}]: {status_text} "
        f"(Adjusted by {quantity}, Current: {current_stock}, Target: {desired_level})"
    )


def main():
    com_token = get_zoho_commerce_token()
    inv_token = get_zoho_inventory_token()  # Get inventory token

    print("ℹ️ You can type 'exit' at any prompt to stop the script.")

    while True:  # main menu loop
        print("\nChoose SKU input mode:\n1 - Fetch SKUs by Vendor\n2 - Enter/Generate SKU list")
        mode = input("Enter choice: ").strip()
        if mode.lower() == "exit":
            print("⏹️ Script stopped by user.")
            return

        # --- Fetch SKUs by Vendor ---
        if mode == "1":
            sku_list = select_products_by_vendor()
            if sku_list == "exit":
                print("⏹️ Script stopped by user.")
                return

        # --- Enter or Generate SKU list ---
        elif mode == "2":
            _, sku_list = get_sku_list(inv_token)  # unpack returned tuple (mode, skus)

        else:
            print("❌ Invalid choice.")
            continue

        if not sku_list:
            print("❌ No SKUs selected. Try again.")
            continue

        # --- Map inventory SKUs to Commerce products ---
        parent_map = map_inventory_to_commerce(sku_list, com_token)
        if not parent_map:
            print("❌ No matching Commerce products found for selected SKUs.")
            continue

        # --- Perform stock adjustment for this batch ---
        perform_stock_adjustment(com_token, parent_map, inv_token)

        # --- Ask user if they want to go back to main menu ---
        again = input("\nDo you want to adjust another batch of SKUs from main menu? (y/n): ").strip().lower()
        if again != "y":
            print("✅ Exiting script.")
            break


if __name__ == "__main__":
    main()






