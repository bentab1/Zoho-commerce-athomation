import re
import requests
import sys
import time

# =========================
# CONFIGURATION
# =========================
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
DOMAIN = "commerce.zoho.com"  # Change if needed


# =========================
# HELPER FUNCTIONS
# =========================

def log(msg):
    print(f"[INFO] {msg}")

def error(msg):
    print(f"[ERROR] {msg}")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)  # replace non-alphanumeric with dash
    text = text.strip('-')
    if not text:  # fallback if slug empty
        text = "item-" + str(int(time.time()))
    return text

def get_zoho_access_token():
    log("Fetching Zoho access token...")
    url = "https://accounts.zoho.com/oauth/v2/token"
    data = {
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        error(f"Failed to fetch access token: {response.text}")
        sys.exit(1)
    token = response.json().get("access_token")
    if not token:
        error("No access token found in response.")
        sys.exit(1)
    log("Access token retrieved successfully.")
    return token


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
        return skus

    elif mode == "2":
        sku_raw = input("Enter SKUs separated by commas: ").strip()
        skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
        print(f"Using provided SKUs: {skus}")
        return skus
    else:
        print("Invalid mode. Exiting.")
        exit()


def fetch_all_products(headers):
    log("Fetching ALL products from Zoho Commerce...")
    products = []
    page = 1
    while True:
        url = f"https://{DOMAIN}/store/api/v1/products?page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            error(f"Failed to fetch products (page {page}): {response.text}")
            break
        data = response.json()
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(batch)
        page += 1
    log(f"Total products fetched: {len(products)}")
    return products


def get_product_details(headers, product_id):
    url = f"https://{DOMAIN}/store/api/v1/products/{product_id}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        error(f"Failed to fetch product details for {product_id}: {response.text}")
        return None
    return response.json().get("product")


def search_product_by_sku(headers, sku):
    log(f"Searching for product with SKU: {sku}")
    url = f"https://{DOMAIN}/store/api/v1/products?search_text={sku}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        error(f"Failed to search for SKU {sku}: {response.text}")
        return []
    data = response.json()
    products = data.get("products", [])
    if not products:
        log(f"No products found for SKU {sku}")
        return []

    full_products = []
    for p in products:
        parent_id = p.get("parent_item_id")
        if parent_id:
            log(f"SKU {sku} is a variant, fetching parent product {parent_id}")
            parent = get_product_details(headers, parent_id)
            if parent:
                full_products.append(parent)
        else:
            full_products.append(p)
    return full_products


def update_product_title(headers, product, update_type, old_words=None, new_words=None, new_title_override=None, append_text=None):
    product_id = product.get("product_id")
    parent_title = product.get("name")

    # Determine new parent title
    new_parent_title = parent_title
    if update_type == "1" and old_words and new_words:
        old_words_list = [w.strip() for w in old_words.split(",") if w.strip()]
        new_words_list = [w.strip() for w in new_words.split(",") if w.strip()]
        for i, old in enumerate(old_words_list):
            new_word = new_words_list[i % len(new_words_list)]
            new_parent_title = new_parent_title.replace(old, new_word)
    elif update_type == "2" and new_title_override:
        new_parent_title = new_title_override
    elif update_type == "3" and append_text:
        new_parent_title = f"{parent_title} {append_text}"

    if new_parent_title == parent_title:
        log(f"No change needed for parent {product.get('sku')}")
        return

    # Prepare update payload
    parent_url_slug = slugify(new_parent_title)
    parent_data = {
        "name": new_parent_title,
        "url": parent_url_slug
    }
    parent_url = f"https://{DOMAIN}/store/api/v1/products/{product_id}"

    # Try updating the product
    resp = requests.put(parent_url, headers=headers, json=parent_data)
    if resp.status_code == 200:
        log(f"✅ Parent updated: {parent_title} → {new_parent_title}")
    else:
        # Check for duplicate URL error
        if resp.status_code == 400 and "Product URL should be unique" in resp.text:
            error(f"❌ URL '{parent_url_slug}' already exists.")
            custom_url = input("Enter a unique URL slug for this product: ").strip()
            if not custom_url:
                error("No custom URL provided. Skipping update.")
                return
            parent_data["url"] = custom_url
            retry_resp = requests.put(parent_url, headers=headers, json=parent_data)
            if retry_resp.status_code == 200:
                log(f"✅ Parent updated with custom URL: {parent_title} → {new_parent_title}")
            else:
                error(f"❌ Failed to update parent even with custom URL: {retry_resp.text}")
                return
        else:
            error(f"❌ Failed to update parent {product.get('sku')}: {resp.text}")
            return

    # Update variants
    for variant in product.get("variants", []):
        variant_sku = variant.get("sku")
        variant_id = variant.get("id") or variant.get("variant_id")
        if not variant_id:
            error(f"❌ Could not find variant ID for SKU {variant_sku}, skipping...")
            continue
        attributes = variant.get("options", [])
        attr_str = " ".join([attr.get("value") for attr in attributes if attr.get("value")])
        new_variant_name = f"{new_parent_title} {attr_str}".strip()
        v_data = {
            "name": new_variant_name,
            "url": slugify(new_variant_name)
        }
        v_url = f"https://{DOMAIN}/store/api/v1/variants/{variant_id}"
        v_resp = requests.put(v_url, headers=headers, json=v_data)
        if v_resp.status_code == 200:
            log(f"✅ Updated variant {variant_sku}: {variant.get('name')} → {new_variant_name}")
        else:
            error(f"❌ Failed to update variant {variant_sku}: {v_resp.text}")



def update_product_titles(token):
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "X-com-zoho-store-organizationid": ORG_ID,
        "Content-Type": "application/json"
    }

    while True:
        choice = input("Update 1-All products, 2-Specific SKUs: ").strip()
        update_type = input("Update type 1-Replace, 2-Override, 3-Append: ").strip()

        old_word = new_word = new_title_override = append_text = None
        if update_type == "1":
            old_word = input("Word(s) to replace (comma separated): ").strip()
            new_word = input("New word(s) (comma separated or single): ").strip()
        elif update_type == "2":
            new_title_override = input("New title: ").strip()
        elif update_type == "3":
            append_text = input("Text to append: ").strip()
        else:
            error("Invalid update type.")
            sys.exit(1)

        if choice == "1":
            products = fetch_all_products(headers)
            for product in products:
                print(f"\n=== PRODUCT DETAILS ===\nSKU: {product.get('sku')}\nTitle: {product.get('name')}\nVariants: {[v.get('sku') for v in product.get('variants', [])]}")
                confirm = input("Update this product? (y/n): ").strip().lower()
                if confirm == 'y':
                    update_product_title(headers, product, update_type, old_word, new_word, new_title_override, append_text)
        elif choice == "2":
            skus = get_sku_list()
            for sku in skus:
                products = search_product_by_sku(headers, sku)
                for product in products:
                    full_details = get_product_details(headers, product.get("product_id"))
                    if full_details:
                        print(f"\n=== PRODUCT DETAILS ===\nSKU: {full_details.get('sku')}\nTitle: {full_details.get('name')}\nVariants: {[v.get('sku') for v in full_details.get('variants', [])]}")
                        confirm = input("Update this product? (y/n): ").strip().lower()
                        if confirm == 'y':
                            update_product_title(headers, full_details, update_type, old_word, new_word, new_title_override, append_text)
        else:
            error("Invalid choice.")
            sys.exit(1)

        again = input("\nDo you want to update another product? (y/n): ").strip().lower()
        if again != 'y':
            log("Exiting script.")
            break


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    try:
        token = get_zoho_access_token()
        update_product_titles(token)
    except Exception as e:
        error(f"Unexpected error: {e}")
