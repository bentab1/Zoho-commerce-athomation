import requests
import time
import json

# Configuration
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = 891730368

def get_access_token():
    """Use refresh token to get a new access token."""
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print("✅ Access token obtained.")
        return token
    else:
        print(f"❌ Failed to get access token: {response.status_code} {response.text}")
        return None

def wait_and_retry(response, max_retries=5):
    retries = 0
    while response.status_code == 429 and retries < max_retries:
        wait_time = int(response.headers.get("Retry-After", 5))
        print(f"Rate limited by Zoho API. Waiting {wait_time} seconds before retrying...")
        time.sleep(wait_time)
        retries += 1
        response = requests.request(
            method=response.request.method,
            url=response.request.url,
            headers=response.request.headers,
            data=response.request.body
        )
    return response.status_code != 429

def fetch_zoho_inventory_items(access_token):
    """Fetch all products/items from Zoho Inventory with pagination."""
    page = 1
    items = []
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    while True:
        url = f"https://inventory.zoho.com/api/v1/items?page={page}&per_page=50&organization_id={ORG_ID}"
        response = requests.get(url, headers=headers)

        # Handle rate limiting
        while not wait_and_retry(response):
            response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to fetch items (Page {page}): {response.status_code} - {response.text}")
            break

        data = response.json()
        item_list = data.get("items", [])
        if not item_list:
            print("No more items found.")
            break

        items.extend(item_list)

        if page == 1 and item_list:
            print("Full example item JSON:\n", json.dumps(item_list[0], indent=4))

        page += 1

    print(f"✅ Total items fetched: {len(items)}")
    return items

def fetch_vendor_items(access_token):
    """Fetch vendor-items associations with pagination from Zoho Inventory."""
    page = 1
    vendor_items = []
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    while True:
        url = f"https://inventory.zoho.com/api/v1/vendoritems?organization_id={ORG_ID}&page={page}&per_page=50"
        response = requests.get(url, headers=headers)

        while not wait_and_retry(response):
            response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to fetch vendor-items (Page {page}): {response.status_code} - {response.text}")
            break

        data = response.json()
        vendor_item_list = data.get("vendoritems", [])
        if not vendor_item_list:
            print("No more vendor-items found.")
            break

        vendor_items.extend(vendor_item_list)
        page += 1

    print(f"✅ Total vendor-items fetched: {len(vendor_items)}")
    return vendor_items

def merge_items_with_preferred_vendor(items, vendor_items):
    """Add preferred vendor info to each item dictionary if available."""
    preferred_vendor_map = {}
    for vi in vendor_items:
        if vi.get("is_preferred_vendor", False):
            preferred_vendor_map[vi["item_id"]] = {
                "vendor_id": vi.get("vendor_id"),
                "vendor_name": vi.get("vendor_name"),
            }

    count_with_vendor = 0
    for item in items:
        pref_vendor = preferred_vendor_map.get(item.get("item_id"))
        item["preferred_vendor"] = pref_vendor if pref_vendor else None
        if pref_vendor:
            count_with_vendor += 1

    print(f"ℹ️ Preferred vendor info added to {count_with_vendor} out of {len(items)} items.")
    return items

if __name__ == "__main__":
    token = get_access_token()
    if token:
        items = fetch_zoho_inventory_items(token)
        vendor_items = fetch_vendor_items(token)
        items_with_vendors = merge_items_with_preferred_vendor(items, vendor_items)
        print(json.dumps(items_with_vendors[0], indent=4))
