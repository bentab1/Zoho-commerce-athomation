import requests
import os

# CONFIGURATION
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
base_url = "https://commerce.zoho.com/store/api/v1"
SESSION = requests.Session()
PRODUCT_CACHE = None




def get_zoho_access_token():
    """Fetch Zoho OAuth access token using the refresh token."""
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


def get_product_id_by_sku(sku, access_token):
    """Return product ID by SKU (top-level or variant)."""
    base_url = "https://commerce.zoho.com/store/api/v1"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}", "X-com-zoho-commerce-organizationid": ORG_ID}
    page = 1
    while True:
        res = requests.get(f"{base_url}/products?page={page}&per_page=200&organization_id={ORG_ID}", headers=headers)
        if res.status_code != 200:
            print(f"❌ Failed to fetch products: {res.status_code} {res.text}")
            return None
        products = res.json().get("products", [])
        if not products:
            break
        for product in products:
            if product.get("sku", "").strip().upper() == sku.strip().upper():
                return product.get("product_id")
            for variant in product.get("variants", []):
                if variant.get("sku", "").strip().upper() == sku.strip().upper():
                    return product.get("product_id")
        page += 1
    return None

def get_all_brands(access_token, ORG_ID):
    """
    Fetch all brands from Zoho Commerce and return a dictionary
    mapping brand name -> brand_id
    """
    import requests

    url = f"https://commerce.zoho.com/store/api/v1/brands?organization_id={ORG_ID}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": ORG_ID,
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch brands: {response.status_code} {response.text}")
        return {}

    data = response.json()
    brands = data.get("brands", [])

    # Build mapping: brand_name -> brand_id
    brand_map = {b["name"].strip(): b["brand_id"] for b in brands if "name" in b and "brand_id" in b}
    return brand_map


def input_brand(access_token, current_brand=""):
    """Prompt user to enter a brand and validate against existing brands (case-insensitive)."""
    brands = get_all_brands(access_token,ORG_ID)
    
    if not brands:
        print("⚠️ No brands found in the store. You can enter any value.")
        return input(f"Brand [{current_brand}]: ").strip() or current_brand

    # Create a mapping for case-insensitive matching
    brands_map = {b.lower(): b for b in brands}

    while True:
        brand_input = input(f"Brand [{current_brand}]: ").strip()
        
        if not brand_input:  # Keep current
            return current_brand
        
        brand_lower = brand_input.lower()
        if brand_lower in brands_map:
            return brands_map[brand_lower]
        
        # Invalid brand
        print("❌ Invalid brand!")
        print("Available brands in store:")
        print(", ".join(brands))
        print("Please enter a valid brand or press Enter to skip.")



def get_product_id_by_sku(sku, access_token):
    """Return product ID by SKU (top-level or variant), using cached product list for speed."""
    global PRODUCT_CACHE

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": ORG_ID
    }

    # ✅ Fetch all products once and cache them
    if PRODUCT_CACHE is None:
        PRODUCT_CACHE = []
        page = 1
        while True:
            res = SESSION.get(f"{base_url}/products?page={page}&per_page=200&organization_id={ORG_ID}", headers=headers)
            if res.status_code != 200:
                print(f"❌ Failed to fetch products: {res.status_code} {res.text}")
                break
            products = res.json().get("products", [])
            if not products:
                break
            PRODUCT_CACHE.extend(products)
            page += 1
        print(f"✅ Cached {len(PRODUCT_CACHE)} products for SKU lookup")

    # ✅ Lookup in cache instead of hitting API again
    sku = sku.strip().upper()
    for product in PRODUCT_CACHE:
        if product.get("sku", "").strip().upper() == sku:
            return product.get("product_id")
        for variant in product.get("variants", []):
            if variant.get("sku", "").strip().upper() == sku:
                return product.get("product_id")

    return None




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



def build_update_payload(mode, scope, fields_choice):
    """
    Build JSON payload for updating product fields.
    mode: 1 = append, 2 = overwrite
    scope: 1 = all fields, 2 = selected fields
    fields_choice: list of chosen fields (['seo', 'short', 'full', 'brand'])
    """
    payload = {}

    # --- Example mock field data (replace with your real data source) ---
    seo_data = {
        "seo_title": "Default SEO Title",
        "seo_keyword": "keyword1, keyword2",
        "seo_description": "Default SEO description."
    }
    short_description = {"product_short_description": "<div><p>Short desc here</p></div>"}
    full_description = {"product_description": "<div><p>Full desc here</p></div>"}
    brand_data = {"brand": "HP"}

    # --- Apply scope ---
    if scope == 1:  # update ALL
        payload.update(seo_data)
        payload.update(short_description)
        payload.update(full_description)
        payload.update(brand_data)
    elif scope == 2:  # update selected fields
        if "seo" in fields_choice:
            payload.update(seo_data)
        if "short" in fields_choice:
            payload.update(short_description)
        if "full" in fields_choice:
            payload.update(full_description)
        if "brand" in fields_choice:
            payload.update(brand_data)

    # --- Apply mode (append vs overwrite) ---
    # For now, let's assume append means "merge strings" and overwrite means "replace".
    # You can extend logic here if needed.
    if mode == 1:  
        # append mode (example: add suffix)
        if "seo_title" in payload:
            payload["seo_title"] += " | Extra"
    # mode == 2 just leaves overwrite behavior (default)

    return payload

def update_item_fields_zoho_commerce(product_id, access_token, mode=1, scope=1, input_data=None):
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": ORG_ID,
        "Content-Type": "application/json"
    }
    
    # GET current product data
    res = SESSION.get(f"{base_url}/products/{product_id}?organization_id={ORG_ID}", headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to fetch product data for {product_id}: {res.status_code} {res.text}")
        return None
    product_data = res.json().get("product", {})

    if input_data is None:
        print("⚠️ No input data provided.")
        return None

    # Prepare payload for update
    payload = {}
    for k, v in input_data.items():
        if not v:
            continue
        current_value = product_data.get(k, "")
        payload[k] = (current_value + " " + v) if mode == 1 and current_value else v

    # PUT update request
    res = SESSION.put(f"{base_url}/products/{product_id}?organization_id={ORG_ID}", json=payload, headers=headers)
    if res.status_code not in (200, 201):
        print(f"❌ Update failed for {product_id}: {res.status_code} {res.text}")
        return None

    # Get updated product
    updated_product = res.json().get("product", {})
    print("✅ Product updated successfully!")
    return updated_product


    def process_field(current_value, new_value):
        if not new_value:
            return current_value
        return (current_value + " " + new_value) if mode == 1 and current_value else new_value



    # === SCOPE 1: Update ALL ===
    if scope == 1:
        print("\nUpdating ALL (SEO + Short + Full + Brand):")
        seo_title = input(f"SEO Title [{product_data.get('seo_title', '')}]: ").strip()
        seo_keyword = input(f"SEO Keywords [{product_data.get('seo_keyword', '')}]: ").strip()
        seo_description = input(f"SEO Description [{product_data.get('seo_description', '')}]: ").strip()
        short_desc = input(f"Short Description [{product_data.get('product_short_description', '')}]: ").strip()
        full_desc = input(f"Full Description [{product_data.get('product_description', '')}]: ").strip()
        brand = input(f"Brand [{product_data.get('brand', '')}]: ").strip()

        if seo_title: update_payload["seo_title"] = process_field(product_data.get("seo_title", ""), seo_title)
        if seo_keyword: update_payload["seo_keyword"] = process_field(product_data.get("seo_keyword", ""), seo_keyword)
        if seo_description: update_payload["seo_description"] = process_field(product_data.get("seo_description", ""), seo_description)
        if short_desc: update_payload["product_short_description"] = process_field(product_data.get("product_short_description", ""), short_desc)
        if full_desc: update_payload["product_description"] = process_field(product_data.get("product_description", ""), full_desc)
        if brand: update_payload["brand"] = process_field(product_data.get("brand", ""), brand)

    # === SCOPE 2: Update SELECTED FIELDS ===
    elif scope == 2:
        if not fields_choice:
            print("⚠️ No fields selected.")
            return None

        if "seo" in fields_choice or "1" in fields_choice:
            seo_title = input(f"SEO Title [{product_data.get('seo_title', '')}]: ").strip()
            seo_keyword = input(f"SEO Keywords [{product_data.get('seo_keyword', '')}]: ").strip()
            seo_description = input(f"SEO Description [{product_data.get('seo_description', '')}]: ").strip()
            if seo_title: update_payload["seo_title"] = process_field(product_data.get("seo_title", ""), seo_title)
            if seo_keyword: update_payload["seo_keyword"] = process_field(product_data.get("seo_keyword", ""), seo_keyword)
            if seo_description: update_payload["seo_description"] = process_field(product_data.get("seo_description", ""), seo_description)

        if "short" in fields_choice or "2" in fields_choice:
            short_desc = input(f"Short Description [{product_data.get('product_short_description', '')}]: ").strip()
            if short_desc: update_payload["product_short_description"] = process_field(product_data.get("product_short_description", ""), short_desc)

        if "full" in fields_choice or "3" in fields_choice:
            full_desc = input(f"Full Description [{product_data.get('product_description', '')}]: ").strip()
            if full_desc: update_payload["product_description"] = process_field(product_data.get("product_description", ""), full_desc)

        if "brand" in fields_choice or "4" in fields_choice:
            brand = input_brand(access_token, product_data.get("brand", "")).strip()
            if brand: update_payload["brand"] = process_field(product_data.get("brand", ""), brand)

    if not update_payload:
        print("⚠️ No fields provided. Nothing to update.")
        return None

    # --- Update product ---
    res = requests.put(f"{base_url}/products/{product_id}?organization_id={ORG_ID}", json=update_payload, headers=headers)
    if res.status_code not in (200, 201):
        print(f"❌ Update failed: {res.status_code} {res.text}")
        return None
    
   ##Get response and print item data
    updated_product = res.json().get("product", {})
    print("✅ Product updated successfully!")
    
    # Item name and brand from top level
    # Attempt to fetch name and SKU with fallbacks
    item_name = updated_product.get("name") or updated_product.get("item_name") or "N/A"
    print(f"item_name: {item_name}")
    print(f"brand: {updated_product.get('brand', 'N/A')}")
    
    # SKU from the first variant (if exists)
    variants = updated_product.get("variants", [])
    sku = variants[0].get("sku") if variants else "N/A"
    print(f"sku: {sku}")
    
    # Other fields
    keys_to_print = [
        "category",
        "seo_title",
        "seo_keyword",
        "seo_description",
        "product_short_description",
        "product_description"
    ]
    
    for k in keys_to_print:
        print(f"{k}: {updated_product.get(k, 'N/A')}")
    
    return updated_product


# --- MAIN LOOP ---
if __name__ == "__main__":
    access_token = get_zoho_access_token()
    if not access_token:
        print("⚠️ Could not obtain access token. Please check credentials.")
        exit()

    skus = get_sku_list()
    sku_mode = input("\nDo you want to update:\n1 - All SKUs at once\n2 - One SKU at a time\nEnter choice: ").strip()

    log_file = "update_log.txt"
    with open(log_file, "w", encoding="utf-8") as log:
        log.write("Item Name,SKU,Status\n")
        

    # --- Collect input once for ALL SKUs ---
    if sku_mode == "1":
        print("\nSelect mode: 1 = Add (append), 2 = Overwrite")
        mode = int(input("Mode: ").strip())
        print("\nSelect scope: 1 = Update ALL (SEO+Short+Full+Brand), 2 = Update selected fields")
        scope = int(input("Scope: ").strip())
    
        input_data = {}
        if scope == 1:
            input_data["seo_title"] = input("SEO Title: ").strip()
            input_data["seo_keyword"] = input("SEO Keywords: ").strip()
            input_data["seo_description"] = input("SEO Description: ").strip()
            input_data["product_short_description"] = input("Short Description: ").strip()
            input_data["product_description"] = input("Full Description: ").strip()
            input_data["brand"] = input("Brand: ").strip()
        elif scope == 2:
            print("\nChoose fields to update:")
            print("1 / seo   : SEO fields")
            print("2 / short : Short description")
            print("3 / full  : Full description")
            print("4 / brand : Brand")
            fields_choice = [f.strip().lower() for f in input("Enter comma-separated values: ").strip().split(",")]
            if "seo" in fields_choice or "1" in fields_choice:
                input_data["seo_title"] = input("SEO Title: ").strip()
                input_data["seo_keyword"] = input("SEO Keywords: ").strip()
                input_data["seo_description"] = input("SEO Description: ").strip()
            if "short" in fields_choice or "2" in fields_choice:
                input_data["product_short_description"] = input("Short Description: ").strip()
            if "full" in fields_choice or "3" in fields_choice:
                input_data["product_description"] = input("Full Description: ").strip()
            # if "brand" in fields_choice or "4" in fields_choice:
            #     # Fetch all brands from Zoho
            #     brands = get_all_brands(access_token, ORG_ID)
            #     input_data["brand"] = input("Brand: ").strip()
            if "brand" in fields_choice or "4" in fields_choice:
                # Fetch all brands from Zoho
                brands = get_all_brands(access_token, ORG_ID)
            
                if not brands:
                    print("⚠️ No brands found in the store. You can enter any value.")
                    input_data["brand"] = input("Brand: ").strip()
                else:
                    print("📦 Available brands in store:")
                    for idx, b in enumerate(brands, start=1):
                        print(f"{idx}. {b}")
                    print("👉 Enter a number to select a brand, or type a new name to overwrite.")
            
                    while True:
                        brand_input = input("Brand: ").strip()
            
                        # If user chose a number
                        if brand_input.isdigit():
                            idx = int(brand_input)
                            if 1 <= idx <= len(brands):
                                input_data["brand"] = brands[idx - 1]
                                break
                            else:
                                print("❌ Invalid number. Try again.")
                                continue
            
                        # If user typed text → use as custom brand
                        if brand_input:
                            input_data["brand"] = brand_input
                            break
            
                        # If empty → no brand update
                        input_data["brand"] = ""
                        break
                
        # --- Loop over all SKUs using the same input ---
        for sku in skus:
            product_id = get_product_id_by_sku(sku, access_token)
            if not product_id:
                print(f"❌ SKU not found: {sku}")
                continue
            update_item_fields_zoho_commerce(product_id, access_token, mode=mode, scope=scope, input_data=input_data)


    # --- ONE BY ONE ---
    elif sku_mode == "2":
        for sku in skus:
            product_id = get_product_id_by_sku(sku, access_token)
            if not product_id:
                print(f"❌ SKU {sku} not found in store.")
                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f",{sku},NOT FOUND\n")
                continue
    
            print(f"\n=== Updating SKU {sku} ===")
            print("\nSelect mode: 1 = Add (append), 2 = Overwrite")
            mode = int(input("Mode: ").strip())
            print("\nSelect scope: 1 = Update ALL (SEO+Short+Full+Brand), 2 = Update selected fields")
            scope = int(input("Scope: ").strip())
    
            input_data = {}
    
            if scope == 2:
                print("\nChoose fields to update:")
                print("1 / seo   : SEO fields")
                print("2 / short : Short description")
                print("3 / full  : Full description")
                print("4 / brand : Brand")
                fields_choice = input("Enter comma-separated values: ").strip().split(",")
                fields_choice = [f.strip().lower() for f in fields_choice]
    
                if "seo" in fields_choice or "1" in fields_choice:
                    input_data["seo_title"] = input("SEO Title: ").strip()
                    input_data["seo_keyword"] = input("SEO Keywords: ").strip()
                    input_data["seo_description"] = input("SEO Description: ").strip()
                if "short" in fields_choice or "2" in fields_choice:
                    input_data["product_short_description"] = input("Short Description: ").strip()
                if "full" in fields_choice or "3" in fields_choice:
                    input_data["product_description"] = input("Full Description: ").strip()
                # if "brand" in fields_choice or "4" in fields_choice:
                #     input_data["brand"] = input("Brand: ").strip()
                if "brand" in fields_choice or "4" in fields_choice:
                                # Fetch all brands from Zoho
                                brands = get_all_brands(access_token, ORG_ID)
                            
                                if not brands:
                                    print("⚠️ No brands found in the store. You can enter any value.")
                                    input_data["brand"] = input("Brand: ").strip()
                                else:
                                    print("📦 Available brands in store:")
                                    for idx, b in enumerate(brands, start=1):
                                        print(f"{idx}. {b}")
                                    print("👉 Enter a number to select a brand, or type a new name to overwrite.")
                            
                                    while True:
                                        brand_input = input("Brand: ").strip()
                            
                                        # If user chose a number
                                        if brand_input.isdigit():
                                            idx = int(brand_input)
                                            if 1 <= idx <= len(brands):
                                                input_data["brand"] = brands[idx - 1]
                                                break
                                            else:
                                                print("❌ Invalid number. Try again.")
                                                continue
                            
                                        # If user typed text → use as custom brand
                                        if brand_input:
                                            input_data["brand"] = brand_input
                                            break
                            
                                        # If empty → no brand update
                                        input_data["brand"] = ""
                                        break
    
            else:  # scope == 1 (all fields)
                input_data["seo_title"] = input("SEO Title: ").strip()
                input_data["seo_keyword"] = input("SEO Keywords: ").strip()
                input_data["seo_description"] = input("SEO Description: ").strip()
                input_data["product_short_description"] = input("Short Description: ").strip()
                input_data["product_description"] = input("Full Description: ").strip()
                input_data["brand"] = input("Brand: ").strip()
    
            updated_product = update_item_fields_zoho_commerce(product_id, access_token, mode, scope, input_data)


            if updated_product:
                product_name = updated_product.get("name", "").replace(",", " ")
                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f"{product_name},{sku},UPDATED\n")
            else:
                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f",{sku},FAILED\n")

    print(f"\n📄 Update log saved to {log_file}")
