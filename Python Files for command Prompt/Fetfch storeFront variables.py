import requests
import json

# ------------------- Credentials -------------------
ZOHO_COM_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_COM_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_COM_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"

BASE_URL = "https://commerce.zoho.com/api/v1"
ORG_ID = "891730368"  # Your Organization ID

# ------------------- Authentication -------------------
def get_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_COM_REFRESH_TOKEN,
        "client_id": ZOHO_COM_CLIENT_ID,
        "client_secret": ZOHO_COM_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, params=params)
    data = response.json()
    token = data.get("access_token")
    if not token:
        print("❌ Failed to get access token:", data)
    return token

# ------------------- Helper Function -------------------
def make_request(method, endpoint, access_token, payload=None):
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    url = f"{BASE_URL}/{endpoint}"
    if method.lower() == "get":
        return requests.get(url, headers=headers).json()
    elif method.lower() == "post":
        return requests.post(url, headers=headers, json=payload).json()
    elif method.lower() == "put":
        return requests.put(url, headers=headers, json=payload).json()
    elif method.lower() == "delete":
        return requests.delete(url, headers=headers).json()
    else:
        raise ValueError("Invalid HTTP method")

# ------------------- Storefront / Theme -------------------
def fetch_storefront(access_token):
    print("\nFetching Storefront / Theme Variables...")
    stores_data = make_request("get", f"organizations/{ORG_ID}/stores", access_token)
    stores = stores_data.get("stores", [])
    if not stores:
        print("⚠️ No stores found for this organization.")
        return []

    storefront_data = []
    for store in stores:
        store_id = store.get("store_id")
        store_name = store.get("store_name")
        print(f"\n--- Store: {store_name} (ID: {store_id}) ---")

        store_details = make_request("get", f"stores/{store_id}", access_token)
        theme_settings = store_details.get("store", {}).get("theme_settings", {})
        if theme_settings:
            print("Theme / Storefront Variables:")
            for key, value in theme_settings.items():
                print(f"{key}: {value}")
        else:
            print("⚠️ No theme settings found for this store.")

        storefront_data.append({"store_id": store_id, "store_name": store_name, "theme_settings": theme_settings})
    return storefront_data

def update_theme_variable(access_token, store_id, variable_key, new_value):
    # Fetch current theme_settings first
    store_details = make_request("get", f"stores/{store_id}", access_token)
    theme_settings = store_details.get("store", {}).get("theme_settings", {})
    if not theme_settings:
        theme_settings = {}

    # Update the specific variable
    theme_settings[variable_key] = new_value
    payload = {"theme_settings": theme_settings}
    response = make_request("put", f"stores/{store_id}", access_token, payload)
    print(f"Update Response for {variable_key}: {response}")

# ------------------- Main Menu -------------------
def main():
    access_token = get_access_token()
    if not access_token:
        return
    print("✅ Access token fetched successfully!")

    while True:
        print("\n===== Zoho Storefront Management =====")
        print("1. Fetch Storefront Variables")
        print("2. Update Theme Variable")
        print("0. Exit")
        choice = input("Enter choice: ").strip()

        if choice == "1":
            fetch_storefront(access_token)
        elif choice == "2":
            store_id = input("Enter Store ID: ").strip()
            variable_key = input("Enter theme variable key to update: ").strip()
            new_value = input("Enter new value: ").strip()
            update_theme_variable(access_token, store_id, variable_key, new_value)
        elif choice == "0":
            print("Exiting...")
            break
        else:
            print("Invalid choice! Try again.")

if __name__ == "__main__":
    main()
