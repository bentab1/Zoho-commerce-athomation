import requests

# CONFIG
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
BASE_URL = "https://commerce.zoho.com/store/api/v1"

def get_zoho_access_token():
    print("🔄 Fetching Zoho access token...")
    resp = requests.post(
        "https://accounts.zoho.com/oauth/v2/token",
        data={
            "refresh_token": ZOHO_REFRESH_TOKEN,
            "client_id": ZOHO_CLIENT_ID,
            "client_secret": ZOHO_CLIENT_SECRET,
            "grant_type": "refresh_token"
        }
    )
    data = resp.json()
    if "access_token" in data:
        print("✅ Access token retrieved successfully!")
        return data["access_token"]
    print(f"❌ Failed: {data}")
    return None

def fetch_entities(entity_type, access_token):
    """Fetch all categories or collections"""
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": ORG_ID
    }
    res = requests.get(f"{BASE_URL}/{entity_type}?organization_id={ORG_ID}", headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to fetch {entity_type}: {res.status_code} {res.text}")
        return []
    return res.json().get(entity_type, [])

def select_entities(entities, entity_type):
    """Display entities and let user choose one or multiple"""
    print(f"\nFound {len(entities)} {entity_type}:")
    for idx, ent in enumerate(entities, start=1):
        print(f"{idx}: {ent.get('name', 'Unnamed')}")
    choice = input(f"Enter the number(s) of {entity_type} to update (comma-separated): ").strip()
    indices = [int(x)-1 for x in choice.split(",") if x.strip().isdigit()]
    selected = [entities[i] for i in indices if 0 <= i < len(entities)]
    return selected

def update_entity_seo(access_token, entity_type, entity, all_entities):
    entity_id_field = "category_id" if entity_type=="categories" else "collection_id"
    entity_id = entity.get(entity_id_field)
    if not entity_id:
        print("❌ No ID found. Skipping.")
        return

    # Get current SEO from fetched entities
    current_entity = next((e for e in all_entities if e.get(entity_id_field) == entity_id), {})

    print(f"\n— {entity_type[:-1].capitalize()}: {current_entity.get('name')} (ID: {entity_id}) —")
    print("📄 Current SEO fields:")
    print(f"Title: {current_entity.get('seo_title','')}")
    print(f"Keywords: {current_entity.get('seo_keyword','')}")
    print(f"Description: {current_entity.get('seo_description','')}\n")

    mode_input = input("Mode: 1=Append, 2=Overwrite: ").strip()
    mode = "append" if mode_input=="1" else "overwrite"

    def process_field(field_name, current_value):
        user_input = input(f"{field_name} [{current_value}]: ").strip()
        if mode=="append":
            return " ".join(filter(None, [current_value.strip(), user_input.strip()])) if user_input else current_value
        else:
            return user_input

    payload = {
        "seo_title": process_field("SEO Title", current_entity.get("seo_title","")),
        "seo_keyword": process_field("SEO Keywords", current_entity.get("seo_keyword","")),
        "seo_description": process_field("SEO Description", current_entity.get("seo_description",""))
    }

    if not any(payload.values()):
        print("⚠️ No changes. Skipping.")
        return

    url = f"{BASE_URL}/{entity_type}/{entity_id}?organization_id={ORG_ID}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

    print(f"📦 Sending payload: {payload}")
    res = requests.put(url, headers=headers, json=payload)
    if res.status_code not in (200,201):
        print(f"❌ Update failed: {res.status_code} {res.text}")
        return

    updated = res.json().get(entity_type[:-1], {})
    print("✅ Updated successfully!")
    for k in ["seo_title","seo_keyword","seo_description"]:
        print(f"{k}: {updated.get(k)}")

# --- MAIN ---
if __name__ == "__main__":
    access_token = get_zoho_access_token()
    if not access_token:
        exit()

    print("\nSelect entity type to update:\n1 - Categories\n2 - Collections")
    choice = input("Enter 1 or 2: ").strip()
    entity_type = "categories" if choice=="1" else "collections"

    entities = fetch_entities(entity_type, access_token)
    if not entities:
        print(f"No {entity_type} found.")
        exit()

    selected_entities = select_entities(entities, entity_type)
    for entity in selected_entities:
        update_entity_seo(access_token, entity_type, entity, entities)
