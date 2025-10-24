import requests
import json
import openpyxl
from openpyxl import Workbook
from datetime import datetime
import sys
import time

print("🚀 Script started")

# 🔐 Zoho API Credentials
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"

# Inventory API creds (same org, diff refresh token if needed)
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"

# -------------------------------
# TOKENS
# -------------------------------
def get_zoho_access_token(refresh_token=ZOHO_REFRESH_TOKEN):
    resp = requests.post("https://accounts.zoho.com/oauth/v2/token", data={
        "refresh_token": refresh_token,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    raise Exception(f"Failed to get access token: {data}")

# -------------------------------
# MARKUP & COST FUNCTIONS
# -------------------------------
def prompt_markup_rates():
    tier1 = float(input("Markup for ≤ ₦500,000 (e.g. 16): "))
    tier2 = float(input("Markup for ≤ ₦1,000,000 (e.g. 14): "))
    tier3 = float(input("Markup for > ₦1,000,000 (e.g. 12): "))
    return tier1, tier2, tier3

def reverse_cost(selling_price, t1, t2, t3):
    for m, limit in [(t1, 500000), (t2, 1000000), (t3, float('inf'))]:
        cost_price = selling_price / (1 + m / 100)
        if cost_price <= limit:
            return round(cost_price), m
    return None, None

# -------------------------------
# ZOHO COMMERCE FUNCTIONS
# -------------------------------
def fetch_zoho_products(token):
    products, page = [], 1
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-com-zoho-store-organizationid": ORG_ID
    }
    while True:
        resp = requests.get(
            f"https://commerce.zoho.com/store/api/v1/products?page={page}&per_page=200",
            headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("products"):
            break
        products.extend(data["products"])
        if not data.get("page_context", {}).get("has_more_page"):
            break
        page += 1
    return products

def update_variant_purchase_rate(token, product_id, variant_id, new_rate):
    url = f"https://commerce.zoho.com/store/api/v1/products/{product_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-com-zoho-store-organizationid": ORG_ID,
        "Content-Type": "application/json"
    }
    payload = {"variants": [{"variant_id": variant_id, "purchase_rate": new_rate}]}
    resp = requests.put(url, headers=headers, json=payload)
    return resp.status_code in range(200, 300), resp.text

# -------------------------------
# INVENTORY FUNCTIONS
def fetch_all_vendors(token):
    vendors = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/contacts?page={page}&per_page=200&type=vendor&organization_id={ORG_ID}"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        resp = requests.get(url, headers=headers).json()
        if "contacts" not in resp:
            break
        vendors.extend([v for v in resp["contacts"] if v.get("contact_type") == "vendor"])
        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return vendors

def select_vendor(token):
    vendors = fetch_all_vendors(token)
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

def fetch_inventory_items(token, vendor_id=None):
    items = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/items?organization_id={ORG_ID}&page={page}&per_page=200"
        if vendor_id:
            url += f"&vendor_id={vendor_id}"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        resp = requests.get(url, headers=headers).json()
        if "items" not in resp:
            break
        for i in resp["items"]:
            items.append({"sku": i.get("sku","").upper(), "name": i.get("name","")})
        if not resp.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return items

def fetch_inventory_items_by_vendor(vendor_id, token):
    items = []
    page = 1
    while True:
        url = f"https://inventory.zoho.com/api/v1/items?organization_id={ORG_ID}&vendor_id={vendor_id}&per_page=200&page={page}"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        items_page = data.get("items", [])
        if not items_page:
            break
        items.extend([i.get("sku", "").upper() for i in items_page if i.get("sku")])
        if not data.get("page_context", {}).get("has_more_page"):
            break
        page += 1
    return items

# -------------------------------
# SKU INPUT FUNCTION
# -------------------------------
def get_sku_list():
    mode = input("Choose SKU input mode:\n1 - Generate SKUs\n2 - Provide SKU list (comma separated)\nEnter choice (1 or 2): ").strip()
    if mode == "1":
        prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
        item_name = input("Enter item name (e.g. IP): ").strip()
        start = int(input("Enter start number (e.g. 1): ").strip())
        end = int(input("Enter end number (e.g. 10): ").strip())
        mid_code = item_name.upper()[:2]
        pad_option = input("Choose padding type:\n1 - Fixed 6-digit zero padding\n2 - No padding\n3 - Dynamic padding\nEnter choice: ").strip()
        if pad_option == "1":
            pad_len = 6
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
        elif pad_option == "2":
            skus = [f"{prefix}-{mid_code}-{num}" for num in range(start, end + 1)]
        elif pad_option == "3":
            pad_len = max(len(str(start)), len(str(end)))
            skus = [f"{prefix}-{mid_code}-{str(num).zfill(pad_len)}" for num in range(start, end + 1)]
        else:
            print("Invalid padding option. Exiting.")
            sys.exit()
        return [s.upper() for s in skus]
    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        return [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
    else:
        print("Invalid mode. Exiting.")
        sys.exit()

# -------------------------------
# MAIN FUNCTION
# -------------------------------
def main():
    mode = input("Choose mode:\n1 - By SKU list\n2 - By Vendor\n3 - All Products\nEnter choice: ").strip()
    if mode == "1":
        skus = get_sku_list()
    elif mode == "2":
        inv_token = get_zoho_access_token(ZOHO_INV_REFRESH_TOKEN)
        vendor_id = select_vendor(inv_token)
        if not vendor_id:
            print("❌ No vendor selected. Exiting this run.")
            return
        skus = fetch_inventory_items_by_vendor(vendor_id, inv_token)
        print(f"Fetched {len(skus)} SKUs for Vendor {vendor_id}")
    elif mode == "3":
        skus = None  # Flag meaning "process everything"
        print("⚡ Processing ALL products (no SKU/Vendor filter)")
    else:
        print("Invalid mode. Exiting.")
        return

    t1, t2, t3 = prompt_markup_rates()
    token = get_zoho_access_token()
    products = fetch_zoho_products(token)

    wb = Workbook()
    ws = wb.active
    ws.append(["Product Name", "Variant Name", "SKU", "Selling Price", "New Purchase Rate", "Markup (%)", "Status"])

    matched = set()
    counter = 1

    for p in products:
        pid, pname = p.get("product_id"), p.get("document_name")
        for v in p.get("variants", []):
            sku, sp = v.get("sku"), v.get("rate")
            vid = v.get("variant_id")

            if skus is not None and (not sku or sku.upper() not in skus):
                continue

            if sku:
                matched.add(sku.upper())

            if not sp:
                status, new_rate, markup_used = "Skipped (no SP)", "", ""
            else:
                cost, markup_used = reverse_cost(float(sp), t1, t2, t3)
                if cost is None:
                    status, new_rate, markup_used = "Skip (reverse calc failed)", "", ""
                else:
                    success, respmsg = update_variant_purchase_rate(token, pid, vid, cost)
                    status = "Success" if success else f"Failed: {respmsg}"
                    new_rate = cost
                    print(f"[{counter}] {pname} - {v.get('name')} (SKU: {sku}) | SP: {sp} → Cost: {cost} | Markup: {markup_used}% | Status: {status}")
                    counter += 1

            ws.append([pname, v.get("name"), sku, sp, new_rate, markup_used, status])

    if skus is not None:
        for sku in skus:
            if sku.upper() not in matched:
                ws.append(["", "", sku, "", "", "", "Not found"])
                print(f"❗ SKU not found in product list: {sku}")

    filename = f"UpdateCostPrice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    print(f"✅ Completed. File saved: {filename}")

def run_once():
    try:
        main()
    except Exception as e:
        print(f"❌ Script crashed due to: {e}")

if __name__ == "__main__":
    while True:
        run_once()
        again = input("\n🔄 Do you want to perform another price update? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("👋 Exiting. No further updates will be performed.")
            break
