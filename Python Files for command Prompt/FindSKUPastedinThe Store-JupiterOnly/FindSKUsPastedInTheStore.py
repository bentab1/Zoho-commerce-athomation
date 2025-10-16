import requests
import pandas as pd
import re
from datetime import datetime
# -------------------------------
# Zoho Commerce credentials
# -------------------------------
ZOHO_COM_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_COM_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_COM_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
API_BASE_URL = "https://commerce.zoho.com/store/api/v1"

# -------------------------------
# Helper functions
# -------------------------------
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
        raise Exception(f"Failed to get token: {data}")

def fetch_all_products(access_token):
    """Fetch all products and variants from Zoho Commerce"""
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-store-organizationid": ORG_ID
    }
    products = []
    page = 1
    while True:
        url = f"{API_BASE_URL}/products?page={page}&per_page=200"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Failed to fetch products: {resp.status_code}")
            break
        data = resp.json()
        if not data.get("products"):
            break
        products.extend(data["products"])
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return products

def parse_skus(raw_input):
    """Split pasted input by comma, newline, tab, or space and keep full SKU with dashes"""
    normalized = re.sub(r"[\s]+", ",", raw_input.strip())
    skus = [s.strip().upper() for s in normalized.split(",") if s.strip()]
    return skus

def lookup_skus(products, skus):
    """Match SKUs to products and variants"""
    found = []
    not_found = []

    sku_map = {}
    for p in products:
        pid = p.get("product_id")
        pname = p.get("name")
        main_sku = p.get("sku")
        if main_sku:
            sku_map[main_sku.upper()] = {
                "product_id": pid, "product_name": pname,
                "variant_id": None, "variant_name": None
            }
        for v in p.get("variants", []):
            v_sku = v.get("sku")
            if v_sku:
                sku_map[v_sku.upper()] = {
                    "product_id": pid, "product_name": pname,
                    "variant_id": v.get("variant_id"), "variant_name": v.get("name")
                }

    for idx, sku in enumerate(skus, start=1):
        if sku in sku_map:
            info = sku_map[sku]
            info["serial"] = idx
            info["sku"] = sku
            found.append(info)
        else:
            not_found.append({"serial": idx, "sku": sku})

    return found, not_found

# def save_to_excel(found, not_found, filename="found_skus1.xlsx"):
#     """Save found and not found SKU details to Excel in separate sheets"""
#     with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
#         if found:
#             df_found = pd.DataFrame(found)
#             df_found = df_found[["serial", "sku", "product_name", "variant_name", "product_id", "variant_id"]]
#             df_found.to_excel(writer, sheet_name="Found_SKUs", index=False)
#         if not_found:
#             df_not_found = pd.DataFrame(not_found)
#             df_not_found = df_not_found[["serial", "sku"]]
#             df_not_found.to_excel(writer, sheet_name="Not_Found_SKUs", index=False)
#     print(f"✅ Found and not found SKUs saved to {filename}")
import pandas as pd
from datetime import datetime

def save_to_excel(found, not_found):
    """Save found and not found SKU details to Excel in separate sheets with unique filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"found_skus_{timestamp}.xlsx"

    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        if found:
            df_found = pd.DataFrame(found)
            df_found = df_found[["serial", "sku", "product_name", "variant_name", "product_id", "variant_id"]]
            df_found.to_excel(writer, sheet_name="Found_SKUs", index=False)
        if not_found:
            df_not_found = pd.DataFrame(not_found)
            df_not_found = df_not_found[["serial", "sku"]]
            df_not_found.to_excel(writer, sheet_name="Not_Found_SKUs", index=False)
    
    print(f"✅ Found and not found SKUs saved to {filename}")

# -------------------------------
# Main script
# -------------------------------
def main():
    try:
        access_token = get_zoho_commerce_token()
    except Exception as e:
        print(f"❌ Error getting Zoho token: {e}")
        return

    print("Fetching all products from Zoho Commerce. Please wait...")
    products = fetch_all_products(access_token)
    print(f"✅ Total products fetched: {len(products)}")

    raw_input_skus = input("Paste your SKUs (comma/newline/space separated):\n")
    skus = parse_skus(raw_input_skus)
    print(f"Total SKUs pasted: {len(skus)}")

    found, not_found = lookup_skus(products, skus)

    # Display not found SKUs
    if not_found:
        print("\n⚠️ SKUs not found:")
        for item in not_found:
            print(f"{item['serial']}. {item['sku']}")

    # Save both found and not found SKUs to Excel
    save_to_excel(found, not_found)

    # Summary of SKUs
    print("\n📊 Summary:")
    print(f"Total SKUs pasted: {len(skus)}")
    print(f"Total SKUs found in store: {len(found)}")
    print(f"Total SKUs not found in store: {len(not_found)}")

if __name__ == "__main__":
    main()
