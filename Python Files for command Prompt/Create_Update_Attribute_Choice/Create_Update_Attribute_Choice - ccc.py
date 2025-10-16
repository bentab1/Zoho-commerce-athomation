import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy

# ------------------- Credentials -------------------
# Commerce API
ZOHO_COM_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_COM_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_COM_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
API_BASE_URL = "https://commerce.zoho.com/store/api/v1"
ORG_ID = "891730368"

# Inventory API
ZOHO_INV_CLIENT_ID = ZOHO_COM_CLIENT_ID
ZOHO_INV_CLIENT_SECRET = ZOHO_COM_CLIENT_SECRET
ZOHO_INV_REFRESH_TOKEN = "1000.89243e274b1607f4b1b23760417ca19c.ba478a62cdc32ce464c074ec84b6b38a"
INV_API_BASE = "https://inventory.zoho.com/api/v1"


# ------------------- Tokens -------------------
def get_token(client_id, client_secret, refresh_token):
    payload = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token"
    }
    resp = requests.post("https://accounts.zoho.com/oauth/v2/token", data=payload)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    print("❌ Failed to get token:", data)
    return None


def get_zoho_commerce_token():
    return get_token(ZOHO_COM_CLIENT_ID, ZOHO_COM_CLIENT_SECRET, ZOHO_COM_REFRESH_TOKEN)


def get_zoho_inventory_token():
    return get_token(ZOHO_INV_CLIENT_ID, ZOHO_INV_CLIENT_SECRET, ZOHO_INV_REFRESH_TOKEN)


# ------------------- Vendor fetching -------------------
def fetch_all_vendors(inv_token):
    vendors, page = [], 1
    while True:
        url = f"{INV_API_BASE}/contacts"
        params = {"page": page, "per_page": 200, "type": "vendor", "organization_id": ORG_ID}
        headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if "contacts" not in data:
            print("❌ Error fetching vendors:", data)
            return []
        vendors.extend([v for v in data["contacts"] if v.get("contact_type") == "vendor"])
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1
    return vendors


def select_vendor():
    inv_token = get_zoho_inventory_token()
    if not inv_token:
        return None, []

    vendors = fetch_all_vendors(inv_token)
    if not vendors:
        print("❌ No vendors found.")
        return None, []

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
        return None, []

    # Fetch vendor items (use SKU for Commerce mapping)
    vendor_items, page = [], 1
    while True:
        url = f"{INV_API_BASE}/items"
        params = {"vendor_id": vendor_id, "organization_id": ORG_ID, "page": page, "per_page": 200}
        headers = {"Authorization": f"Zoho-oauthtoken {inv_token}"}
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if "items" not in data:
            print("❌ Error fetching items for vendor:", data)
            return None, []
        for item in data["items"]:
            vendor_items.append({"id": item.get("item_id"), "name": item.get("name", ""), "sku": item.get("sku")})
        if not data.get("page_context", {}).get("has_more_page", False):
            break
        page += 1

    if not vendor_items:
        print("❌ No inventory items found for this vendor.")
        return vendor_id, []

    print("\nVendor Inventory Items:")
    for idx, item in enumerate(vendor_items, 1):
        print(f"{idx}. {item['name']} (SKU: {item['sku']}, ID: {item['id']})")

    # Return SKUs for filtering Commerce products
    return vendor_id, [item["sku"] for item in vendor_items if item.get("sku")]


# ------------------- Commerce product fetching -------------------

def fetch_products(token, filter_skus=None, max_workers=2, max_retries=3, delay_between_requests=0.2):
    """
    Fetch Zoho Commerce products with attributes, choices, and variant counts.
    - filter_skus: List of SKUs to filter. If None, fetch all products.
    """
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    products_data = []
    filter_skus = set(filter_skus) if filter_skus else None

def fetch_products(token, filter_skus=None, max_workers=1, max_retries=5, delay_between_requests=0.5):
    """
    Fetch Zoho Commerce products safely with rate-limit handling.
    - filter_skus: List of SKUs to filter (optional)
    - max_workers: concurrency for fetching product details
    - max_retries: retries per product if rate-limited
    - delay_between_requests: delay between product requests to reduce rate-limit hits
    """
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    products_data = []
    filter_skus_set = {s.strip().upper() for s in filter_skus} if filter_skus else None

    def safe_get(url, params=None):
        """GET request with retry for rate-limiting"""
        wait = 2
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    print(f"⏳ Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                    wait *= 2
                else:
                    print(f"⚠️ Error {resp.status_code}: {resp.text}")
                    return None
            except requests.exceptions.Timeout:
                print(f"⏳ Timeout. Retrying {attempt+1}/{max_retries}")
            except Exception as e:
                print(f"❌ Request error: {e}")
            time.sleep(delay_between_requests)
        print("❌ Max retries exceeded for URL:", url)
        return None

    def fetch_product_detail(product_id):
        url = f"{API_BASE_URL}/products/{product_id}"
        data = safe_get(url, params={"organization_id": ORG_ID})
        if not data:
            return None

        details = data.get("product", {})
        variants = details.get("variants", [])
        parent_sku = (details.get("sku") or (variants[0]["sku"] if variants else "N/A")).strip().upper()
        variant_skus = {(v.get("sku") or "").strip().upper() for v in variants}

        # Filter by SKUs if needed
        if filter_skus_set and not (parent_sku in filter_skus_set or variant_skus & filter_skus_set):
            return None

        # Build attribute → choice → count map
        attr_map = {}
        for attr in details.get("attributes", []):
            name = attr.get("name")
            attr_map[name] = {}
            for choice in attr.get("choices", []):
                val = choice.get("value")
                count = sum(
                    1 for v in variants
                    for av in v.get("attributes", [])
                    if av.get("name") == name and av.get("value") == val
                )
                attr_map[name][val] = count

        product_info = {
            "id": details.get("id") or details.get("product_id"),
            "name": details.get("name") or "Unnamed Product",
            "sku": parent_sku,
            "variants_count": len(variants),
            "variants": [
                {
                    "name": v.get("name"),
                    "sku": (v.get("sku") or "").strip().upper(),
                    "attributes": v.get("attributes", [])
                } for v in variants
            ],
            "attributes": [
                {"name": name, "choices": [{"value": val, "variant_count": count} for val, count in choices.items()]}
                for name, choices in attr_map.items()
            ]
        }
        return product_info

    # ------------------- Main pagination -------------------
    page = 1
    product_counter = 0

    while True:
        url = f"{API_BASE_URL}/products"
        params = {"page": page, "per_page": 200, "organization_id": ORG_ID}
        data = safe_get(url, params=params)
        if not data:
            break

        products = data.get("products") or data.get("data", {}).get("products")
        if not products:
            print(f"✅ No more products found on page {page}.")
            break

        # Threaded fetching of product details
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {executor.submit(fetch_product_detail, p.get("id") or p.get("product_id")): p for p in products}

            for future in as_completed(future_to_id):
                product_info = None
                try:
                    product_info = future.result(timeout=15)
                except Exception as e:
                    print(f"⚠️ Failed fetching product: {e}")

                if product_info:
                    products_data.append(product_info)
                    product_counter += 1

                    # Print summary
                    print(f"\n{product_counter}. 📦 {product_info['name']} (Parent SKU: {product_info['sku']})")
                    print(f"   Total Variants: {product_info['variants_count']}")
                    for idx, v in enumerate(product_info["variants"], 1):
                        attrs = ", ".join([f"{a['name']}: {a['value']}" for a in v.get("attributes", [])])
                        print(f"   ├─ {idx}. Variant: {v['name']} | SKU: {v['sku']} | {attrs}")
                    if product_info["attributes"]:
                        print("   Attributes & Choices:")
                        for attr in product_info["attributes"]:
                            print(f"   └─ {attr['name']}:")
                            for choice in attr["choices"]:
                                print(f"      • {choice['value']}")
                    time.sleep(delay_between_requests)

        page += 1

    return products_data

def create_or_update_attribute(token, product_id, attr_name, choices):
    """
    Apply a new attribute to product variants in Zoho Commerce using the correct PUT /variants/ endpoint.
    
    Args:
        token (str): Zoho OAuth token.
        product_id (str): ID of the product to update.
        attr_name (str): Name of the attribute to add/update.
        choices (list): List of values for the attribute.
        
    Returns:
        bool: True if all updates succeed, False otherwise.
    """
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": "application/json"
    }

    # 1️⃣ Fetch existing product and variants
    try:
        resp = requests.get(
            f"{API_BASE_URL}/products/{product_id}",
            headers=headers,
            params={"organization_id": ORG_ID}
        )
        if resp.status_code != 200:
            print(f"⚠️ Failed to fetch product {product_id}: {resp.status_code} {resp.text}")
            return False
        product = resp.json().get("product", {})
        variants = product.get("variants", [])
        if not variants:
            print(f"⚠️ Product {product_id} has no variants.")
            return False
    except Exception as e:
        print(f"❌ Exception fetching product {product_id}: {e}")
        return False

    success = True

    # 2️⃣ Update each variant with the attribute using Zoho's required fields
    for idx, variant in enumerate(variants):
        variant_id = variant.get("id")
        if not variant_id:
            continue

        # Assign choice for this variant (round-robin)
        choice_for_variant = choices[idx % len(choices)]

        # Map existing attributes to Zoho fields
        attribute_payload = {}
        for i, attr in enumerate(variant.get("attributes", []), start=1):
            attribute_payload[f"attribute_option_name{i}"] = attr.get("value")

        # Add new attribute as next available option
        next_index = len(variant.get("attributes", [])) + 1
        attribute_payload[f"attribute_option_name{next_index}"] = choice_for_variant

        payload = {
            "variant": {
                "sku": variant.get("sku"),
                "initial_stock": variant.get("initial_stock", 10),  # required if inventory variant
                "rate": variant.get("rate", "0"),
                **attribute_payload
            }
        }

        try:
            put_resp = requests.put(
                f"{API_BASE_URL}/variants/",
                headers=headers,
                params={"organization_id": ORG_ID},
                json=payload
            )
            if put_resp.status_code not in (200, 201):
                print(f"⚠️ Failed to update variant {variant_id}: {put_resp.status_code} {put_resp.text}")
                success = False
            else:
                print(f"✅ Updated variant {variant_id} with {attr_name}: {choice_for_variant}")
        except Exception as e:
            print(f"❌ Exception updating variant {variant_id}: {e}")
            success = False

    return success


# ------------------- Function to update product title -------------------
def update_product_title(headers, product, update_type, old_word=None, new_word=None, new_title_override=None, append_text=None):
    """
    Update a Zoho Commerce product's title, URL, and its variants.
    """
    product_id = product.get("product_id")
    current_title = product.get("name")
    variants = product.get("variants", [])

    # Decide new title
    new_title = current_title
    if update_type == "1" and old_word and new_word and old_word in current_title:
        new_title = current_title.replace(old_word, new_word)
    elif update_type == "2" and new_title_override:
        new_title = new_title_override
    elif update_type == "3" and append_text:
        new_title = f"{current_title} {append_text}"

    if new_title == current_title:
        print(f"⚠️ No change for product {product_id} ({current_title})")
        return False

    # Generate new URL slug
    new_url = re.sub(r'[^a-z0-9]+', '-', new_title.lower()).strip('-')

    # Update parent product (title + url)
    url = f"https://commerce.zoho.com/store/api/v1/products/{product_id}"
    payload = {"name": new_title, "url": new_url}
    try:
        resp = requests.put(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            print(f"✅ Updated product: '{current_title}' → '{new_title}' (URL: {new_url})")
        else:
            print(f"⚠️ Failed to update product {product_id}: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Exception updating product {product_id}: {e}")
        return False

    # Update variants (keep consistent with parent)
    for variant in variants:
        variant_id = variant.get("product_id")
        current_variant_name = variant.get("name")

        if update_type == "1" and old_word and new_word:
            new_variant_name = current_variant_name.replace(old_word, new_word)
        elif update_type == "2" and new_title_override:
            new_variant_name = current_variant_name.replace(current_title, new_title)
        elif update_type == "3" and append_text:
            new_variant_name = current_variant_name.replace(current_title, f"{current_title} {append_text}")
        else:
            new_variant_name = current_variant_name

        if new_variant_name == current_variant_name:
            continue

        v_url = f"https://commerce.zoho.com/store/api/v1/products/{variant_id}"
        v_payload = {"name": new_variant_name}
        try:
            v_resp = requests.put(v_url, headers=headers, json=v_payload)
            if v_resp.status_code in (200, 201):
                print(f"   ↳ Updated variant: '{current_variant_name}' → '{new_variant_name}'")
            else:
                print(f"⚠️ Failed to update variant {variant_id}: {v_resp.status_code} {v_resp.text}")
        except Exception as e:
            print(f"❌ Exception updating variant {variant_id}: {e}")

    return True

# ------------------- Main -------------------
if __name__ == "__main__":
    try:
        # --- Choose mode ---
        mode_choice = int(input(
            "Choose mode:\n0 - Fetch only\n1 - Update product title\n2 - Update attribute\nEnter choice: "
        ).strip())

        # --- Fetch products by vendor (optional) ---
        use_vendor = input("Fetch products by vendor? (y/n): ").strip().lower()
        vendor_skus = []
        if use_vendor == "y":
            vendor_id, vendor_skus = select_vendor()
            if not vendor_skus:
                print("❌ No products found for the selected vendor. Exiting.")
                exit()

        # --- Get Commerce token ---
        token = get_zoho_commerce_token()
        if not token:
            print("❌ Failed to get Commerce token. Exiting.")
            exit()

        # --- Fetch products ---
        products = fetch_products(token, filter_skus=vendor_skus if use_vendor == "y" else None)
        if not products:
            print("❌ No products to process. Exiting.")
            exit()

        # --- Mode 0: Fetch only ---
        if mode_choice == 0:
            print("\n✅ Fetch completed. Products listed above. Exiting.")
            exit()

        # --- Mode 1: Update Product Title ---
        elif mode_choice == 1:
            while True:
                print("\nAvailable Products:")
                for idx, prod in enumerate(products, 1):
                    print(f"{idx}. {prod['name']} (SKU: {prod['sku']})")

                # Enter new title
                new_title = ""
                while not new_title:
                    new_title = input("\nEnter new product title: ").strip()
                    if not new_title:
                        print("⚠️ Product title cannot be empty. Please try again.")

                # Append or overwrite
                append_choice = ""
                while append_choice not in ("y", "n"):
                    append_choice = input("Append to existing title? (y/n): ").strip().lower()

                # Product selection
                apply_all = ""
                while apply_all not in ("y", "n"):
                    apply_all = input("Apply this title change to all products? (y/n): ").strip().lower()

                if apply_all == "y":
                    selected_numbers = list(range(1, len(products) + 1))
                else:
                    selected_numbers = []
                    while not selected_numbers:
                        product_numbers = input("\nEnter product numbers to update title (comma separated): ").strip()
                        selected_numbers = [int(n.strip()) for n in product_numbers.split(",") if n.strip().isdigit()]
                        if not selected_numbers:
                            print("⚠️ Must select at least one product.")
                            continue
                        invalid_nums = [n for n in selected_numbers if n < 1 or n > len(products)]
                        if invalid_nums:
                            print(f"⚠️ Invalid product numbers: {invalid_nums}. Try again.")
                            selected_numbers = []

                # --- Preview updates ---
                print("\n📋 Preview Title Updates:")
                preview_updates = []
                for num in selected_numbers:
                    prod = products[num - 1]
                    updated_title = new_title if append_choice == "n" else f"{prod['name']} {new_title}"
                    preview_updates.append((prod["name"], updated_title, prod["sku"]))
                    print(f" - {prod['name']} (SKU: {prod['sku']}) → {updated_title}")

                confirm = input("\nProceed with these updates? (y/n): ").strip().lower()
                if confirm != "y":
                    print("⚠️ Update cancelled. Returning to menu.")
                    continue

                # Apply updates
                all_success = True
                for old, updated_title, sku in preview_updates:
                    prod = next(p for p in products if p["sku"] == sku)
                    if not update_product_title(token, prod["id"], updated_title):
                        all_success = False
                        print(f"⚠️ Failed to update {old}.")
                    else:
                        print(f"✅ Updated '{old}' → '{updated_title}'")

                if all_success:
                    print("\n✅ All selected products updated successfully.")

                again = ""
                while again not in ("y", "n"):
                    again = input("\nDo you want to update product title again? (y/n): ").strip().lower()
                if again != "y":
                    print("✅ Finished updating product titles. Exiting.")
                    break

        # --- Mode 2: Update Attributes ---
        elif mode_choice == 2:
            while True:
                # --- Enter attribute name ---
                attr_name = ""
                while not attr_name:
                    attr_name = input("\nEnter attribute name: ").strip()
                    if attr_name.lower() == "exit":
                        print("⏹️ Exiting attribute entry.")
                        exit()
                    if not attr_name:
                        print("⚠️ Attribute name cannot be empty. Please try again.")

                # --- Enter choices ---
                choices = []
                while not choices:
                    raw_choices = input("Enter choices (comma separated): ").strip()
                    choices = [c.strip() for c in raw_choices.split(",") if c.strip()]
                    if not choices:
                        print("⚠️ Must enter at least one choice.")

                # --- Preview attribute ---
                print("\n📋 Preview Attribute:")
                print(f"   Name: {attr_name}")
                print("   Choices:")
                for c in choices:
                    print(f"    • {c}")

                confirm = input("\nDo you want to edit this attribute? (y/n): ").strip().lower()
                if confirm == "y":
                    continue  # restart loop for new attribute

                # --- Product selection ---
                apply_all = ""
                while apply_all not in ("y", "n"):
                    apply_all = input("Apply this attribute to all products? (y/n): ").strip().lower()

                if apply_all == "y":
                    selected_numbers = list(range(1, len(products) + 1))
                else:
                    selected_numbers = []
                    while not selected_numbers:
                        product_numbers = input("\nEnter product numbers to apply attribute (comma separated): ").strip()
                        selected_numbers = [int(n.strip()) for n in product_numbers.split(",") if n.strip().isdigit()]
                        if not selected_numbers:
                            print("⚠️ Must select at least one product.")
                        invalid_nums = [n for n in selected_numbers if n < 1 or n > len(products)]
                        if invalid_nums:
                            print(f"⚠️ Invalid product numbers: {invalid_nums}. Try again.")
                            selected_numbers = []

                # --- Preview attribute application ---
                print("\n📋 Preview Attribute Application:")
                for num in selected_numbers:
                    prod = products[num - 1]
                    print(f" - {prod['name']} (SKU: {prod['sku']}) → Attribute: {attr_name}, Choices: {', '.join(choices)}")

                confirm = input("\nProceed with applying this attribute? (y/n): ").strip().lower()
                if confirm != "y":
                    print("⚠️ Attribute update cancelled. Returning to menu.")
                    continue

                # --- Apply attribute ---
                all_success = True
                for num in selected_numbers:
                    prod = products[num - 1]
                    print(f"🔄 Applying attribute '{attr_name}' to {prod['name']} (SKU: {prod['sku']}) ...")
                    if not create_or_update_attribute(token, prod["id"], attr_name, choices):
                        all_success = False
                        print(f"⚠️ Failed to apply attribute to {prod['name']}.")

                if all_success:
                    print("\n✅ Attribute successfully applied to all selected products.")
                else:
                    print("\n⚠️ One or more attribute updates failed. Please try again.")

                again = input("Do you want to create/update another attribute? (y/n): ").strip().lower()
                if again != "y":
                    print("✅ Finished updating attributes. Exiting.")
                    break

        else:
            print("⚠️ Invalid mode choice. Exiting.")

    except Exception as e:
        print("❌ Error:", e)

