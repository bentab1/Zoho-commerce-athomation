import requests

# =======================
# Configuration
# =======================
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
ORG_ID = 891730368

BASE_URL = "https://inventory.zoho.com/api/v1"

# =======================
# Auth Function
# =======================
def get_access_token():
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
        return token
    else:
        raise Exception(f"Failed to get access token: {response.text}")

# =======================
# Fetch Accounts
# =======================
def get_accounts(access_token):
    url = f"{BASE_URL}/chartofaccounts?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["chartofaccounts"]
    else:
        raise Exception(f"Failed to fetch accounts: {response.text}")

# =======================
# Fetch Items
# =======================
# =======================
# Fetch All Items (with pagination)
# =======================
def get_items(access_token):
    items = []
    page = 1
    per_page = 200  # Max allowed by Zoho
    while True:
        url = f"{BASE_URL}/items?organization_id={ORG_ID}&page={page}&per_page={per_page}"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch items: {response.text}")

        data = response.json()
        batch = data.get("items", [])
        items.extend(batch)

        if len(batch) < per_page:
            break  # No more pages
        page += 1

    return items


# =======================
# Update Item Account
# =======================
def update_item_account(access_token, item, account_id, mode="sales"):
    item_id = item["item_id"]
    sku = item.get("sku", "N/A")  # fallback if SKU missing

    url = f"{BASE_URL}/items/{item_id}?organization_id={ORG_ID}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

    if mode == "sales":
        payload = {"account_id": account_id}
    elif mode == "purchase":
        payload = {"purchase_account_id": account_id}
    else:
        raise Exception("Mode must be 'sales' or 'purchase'")

    response = requests.put(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"✅ Updated item {item_id} (SKU: {sku}) with {mode} account.")
        return True
    else:
        print(f"❌ Failed to update item {item_id} (SKU: {sku}): {response.text}")
        return False

# =======================
# Apply Account to Items
# =======================
# def apply_account_to_items(access_token, account_name, mode, items):
#     if not account_name.strip():
#         print(f"⚠️ Skipped {mode} account update (no account provided).")
#         return 0

#     accounts = get_accounts(access_token)

#     # Find account by name
#     account_id = None
#     for acc in accounts:
#         if acc["account_name"].lower() == account_name.lower():
#             account_id = acc["account_id"]
#             break

#     if not account_id:
#         print(f"❌ Account '{account_name}' not found. Available accounts:")
#         for acc in accounts:
#             print(f"- {acc['account_name']}")
#         return 0

#     # Update all items
#     updated_count = 0
#     for item in items:
#         if update_item_account(access_token, item, account_id, mode=mode):
#             updated_count += 1

#     print(f"📊 Total {mode} updates: {updated_count} items updated.")
#     return updated_count

# =======================
# Apply Account to Items (Numbered Output)
# =======================
def apply_account_to_items(access_token, account_name, mode, items):
    if not account_name.strip():
        print(f"⚠️ Skipped {mode} account update (no account provided).")
        return 0

    accounts = get_accounts(access_token)

    # Find account by name
    account_id = None
    for acc in accounts:
        if acc["account_name"].lower() == account_name.lower():
            account_id = acc["account_id"]
            break

    if not account_id:
        print(f"❌ Account '{account_name}' not found. Available accounts:")
        for acc in accounts:
            print(f"- {acc['account_name']}")
        return 0

    # Update all items with numbering
    updated_count = 0
    for idx, item in enumerate(items, start=1):
        if update_item_account(access_token, item, account_id, mode=mode):
            print(f"{idx}. ✅ Updated item {item['item_id']} (SKU: {item.get('sku', 'N/A')}) with {mode} account.")
            updated_count += 1

    print(f"📊 Total {mode} updates: {updated_count} items updated.")
    return updated_count


# =======================
# Main Script
# =======================
def main():
    access_token = get_access_token()

    # Fetch items once at start
    items = get_items(access_token)
    print(f"📦 Total items in inventory: {len(items)}")

    total_updates = 0

    # Step 1: Ask for Sales Account
    sales_account = input("Enter Sales Account Name (or press Enter to skip): ").strip()
    total_updates += apply_account_to_items(access_token, sales_account, mode="sales", items=items)

    # Step 2: Ask for Purchase Account
    purchase_account = input("Enter Purchase Account Name (or press Enter to skip): ").strip()
    total_updates += apply_account_to_items(access_token, purchase_account, mode="purchase", items=items)

    print(f"✅ Total items updated: {total_updates}")
    print("🎯 Script finished.")

# =======================
# Main Loop
# =======================
def main_loop():
    while True:
        main()
        again = input("Do you want to perform another update? (y/n): ").strip().lower()
        if again != "y":
            print("👋 Exiting script. Goodbye.")
            break

# =======================
# Run
# =======================
if __name__ == "__main__":
    main_loop()
