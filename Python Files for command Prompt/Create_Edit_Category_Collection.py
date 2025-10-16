import requests
import pandas as pd
import os
from datetime import datetime

# -------------------------------
# Config
# -------------------------------
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
LOG_FILE = "Create_Edit_Category_Collection_Log.xlsx"

BASE_URL = "https://commerce.zoho.com/store/api/v1"

# -------------------------------
# Access Token
# -------------------------------
def get_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    response = requests.post(url, params=params)
    return response.json().get("access_token")

# -------------------------------
# Fetch Entity
# -------------------------------
def fetch_entity(entity_type, access_token):
    url = f"{BASE_URL}/{entity_type}?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        items = response.json().get(entity_type, [])
        for i, item in enumerate(items, start=1):
            print(f"{i}. ID: {item.get('category_id') or item.get('collection_id')} | Name: {item.get('name')}")
        return items
    else:
        print(f"Failed to fetch {entity_type}: {response.status_code} {response.text}")
        return []

# -------------------------------
# Create Category/Collection
# -------------------------------
def create_entity(entity_type, access_token):
    name = input(f"Enter new {entity_type[:-1]} name: ").strip()
    payload = {"name": name}

    url = f"{BASE_URL}/{entity_type}?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code in [200, 201]:
        print(f"✅ {entity_type[:-1].capitalize()} '{name}' created successfully!")
        log_action(f"Created {entity_type[:-1]}: {name}")
    else:
        print(f"❌ Failed to create {entity_type[:-1]}: {response.text}")

# -------------------------------
# Edit Category/Collection (Name Only)
# -------------------------------
def edit_entity(entity_type, access_token):
    items = fetch_entity(entity_type, access_token)
    if not items:
        return
    choice = int(input(f"Select {entity_type[:-1]} number to edit: ").strip())
    entity = items[choice-1]

    new_name = input(f"Enter new name for {entity_type[:-1]} '{entity['name']}': ").strip()
    payload = {"name": new_name}

    entity_id = entity.get("category_id") if entity_type == "categories" else entity.get("collection_id")
    url = f"{BASE_URL}/{entity_type}/{entity_id}?organization_id={ORG_ID}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    response = requests.put(url, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"✅ {entity_type[:-1].capitalize()} renamed to '{new_name}' successfully!")
        log_action(f"Edited {entity_type[:-1]}: {entity['name']} -> {new_name}")
    else:
        print(f"❌ Failed to update {entity_type[:-1]}: {response.text}")

# -------------------------------
# Logging
# -------------------------------
def log_action(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = pd.DataFrame([[now, message]], columns=["Timestamp", "Action"])
    if os.path.exists(LOG_FILE):
        df = pd.read_excel(LOG_FILE)
        df = pd.concat([df, log_entry], ignore_index=True)
    else:
        df = log_entry
    df.to_excel(LOG_FILE, index=False)

# -------------------------------
# Main
# -------------------------------
def main():
    access_token = get_access_token()
    print("Access token fetched.")

    mode = input("\nSelect Mode:\n1 - Fetch\n2 - Create\n3 - Edit\nEnter choice: ").strip()
    entity_choice = input("Select Entity:\n1 - Category\n2 - Collection\nEnter choice: ").strip()
    entity_type = "categories" if entity_choice == "1" else "collections"

    if mode == "1":
        fetch_entity(entity_type, access_token)
    elif mode == "2":
        create_entity(entity_type, access_token)
    elif mode == "3":
        edit_entity(entity_type, access_token)
    else:
        print("Invalid mode.")

if __name__ == "__main__":
    main()
