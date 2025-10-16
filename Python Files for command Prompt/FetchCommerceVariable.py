import requests
import json
import time  # <-- Needed for time.sleep()

# -------------------------------
# CONFIGURATION
# -------------------------------
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"

# -------------------------------
# FUNCTIONS
# -------------------------------
def get_zoho_access_token():
    """Get Zoho OAuth access token using refresh token."""
    url = "https://accounts.zoho.com/oauth/v2/token"
    payload = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, data=payload)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    else:
        raise Exception(f"❌ Failed to get access token: {data}")

def wait_and_retry(response):
    """Handle Zoho API rate limits by waiting and retrying."""
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 5))
        print(f"⚠️ Rate limit reached. Retrying after {retry_after} seconds...")
        time.sleep(retry_after)
        return True
    return False

def fetch_all_commerce_products(access_token):
    """Fetch all products from Zoho Commerce and return them."""
    page = 1
    products = []
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    while True:
        url = f"https://commerce.zoho.com/store/api/v1/products?page={page}&per_page=200&organization_id={ORG_ID}"
        response = requests.get(url, headers=headers)

        while wait_and_retry(response):
            response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to fetch products (Page {page}): {response.status_code} - {response.text}")
            break

        data = response.json()
        product_list = data.get("products", [])
        if not product_list:
            print("No more products found.")
            break

        products.extend(product_list)
        page += 1

    return products

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    token = get_zoho_access_token()
    all_products = fetch_all_commerce_products(token)
    
    print(f"✅ Total products fetched: {len(all_products)}")
    print(json.dumps(all_products, indent=4))  # Show all product details
