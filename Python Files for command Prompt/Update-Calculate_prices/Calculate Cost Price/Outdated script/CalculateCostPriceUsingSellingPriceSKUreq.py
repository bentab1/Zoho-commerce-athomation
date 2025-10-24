import requests
import json
import openpyxl
from openpyxl import Workbook
from datetime import datetime
import sys

print("🚀 Script started")

# 🔐 Zoho API Credentials
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"

def get_zoho_access_token():
    print("Fetching Zoho access token...")
    resp = requests.post("https://accounts.zoho.com/oauth/v2/token", data={
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    data = resp.json()
    if "access_token" in data:
        print("✅ Access token retrieved")
        return data["access_token"]
    print(f"❌ Failed to get access token: {data}")
    raise Exception(f"Failed to get access token: {data}")

def prompt_markup_rates():
    print("Prompting for markup rates...")
    tier1 = float(input("Markup for ≤ ₦500,000 (e.g. 16): "))
    tier2 = float(input("Markup for ≤ ₦1,000,000 (e.g. 14): "))
    tier3 = float(input("Markup for > ₦1,000,000 (e.g. 12): "))
    print(f"Markup rates set: {tier1}%, {tier2}%, {tier3}%")
    return tier1, tier2, tier3

def reverse_cost(selling_price, t1, t2, t3):
    # Try each bracket, decide based on cost price
    for m, limit in [(t1, 500000), (t2, 1000000), (t3, float('inf'))]:
        cost_price = selling_price / (1 + m / 100)
        if cost_price <= limit:
            return round(cost_price), m
    return None, None

def fetch_zoho_products(token):
    print("Fetching products from Zoho Commerce...")
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
    print(f"Fetched {len(products)} products")
    return products

def update_variant_purchase_rate(token, product_id, variant_id, new_rate):
    print(f"Updating purchase rate for variant {variant_id} to {new_rate}...")
    url = f"https://commerce.zoho.com/store/api/v1/products/{product_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-com-zoho-store-organizationid": ORG_ID,
        "Content-Type": "application/json"
    }
    payload = {
        "variants": [
            {"variant_id": variant_id, "purchase_rate": new_rate}
        ]
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in range(200, 300):
        print(f"✅ Updated variant {variant_id}")
    else:
        print(f"❌ Failed to update variant {variant_id}: {resp.text}")
    return resp.status_code in range(200, 300), resp.text

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

def main():
    print("Starting SKU update process...")
    _, skus = get_sku_list()
    t1, t2, t3 = prompt_markup_rates()
    token = get_zoho_access_token()
    products = fetch_zoho_products(token)

    wb = Workbook()
    ws = wb.active
    ws.append(["Product Name", "Variant Name", "SKU", "Selling Price", "New Purchase Rate", "Markup (%)", "Status"])

    matched = set()
    counter = 1  # track update order

    for p in products:
        pid, pname = p.get("product_id"), p.get("document_name")
        for v in p.get("variants", []):
            sku, sp = v.get("sku"), v.get("rate")
            vid = v.get("variant_id")
            if not sku or sku.upper() not in map(str.upper, skus):
                continue
            matched.add(sku.upper())
            if not sp:
                status = "Skipped (no SP)"
                new_rate = ""
                markup_used = ""
            else:
                cost, markup_used = reverse_cost(float(sp), t1, t2, t3)
                if cost is None:
                    status = "Skip (reverse calc failed)"
                    new_rate = ""
                    markup_used = ""
                else:
                    success, respmsg = update_variant_purchase_rate(token, pid, vid, cost)
                    status = "Success" if success else f"Failed: {respmsg}"
                    new_rate = cost

                    # 📢 Console log in order
                    print(f"[{counter}] {pname} - {v.get('name')} (SKU: {sku}) | SP: {sp} → Cost: {cost} | Markup: {markup_used}% | Status: {status}")
                    counter += 1

            ws.append([pname, v.get("name"), sku, sp, new_rate, markup_used, status])

    for sku in skus:
        if sku.upper() not in matched:
            ws.append(["", "", sku, "", "", "", "Not found"])
            print(f"❗ SKU not found in product list: {sku}")

    filename = f"Update Cost Price Orginal_usingCommerceWithSKUrequestWorked{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    print(f"✅ Completed. File saved: {filename}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Script crashed due to an unexpected error: {e}")
