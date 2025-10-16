import requests
import json
import sys
import pandas as pd
from slugify import slugify  # <- Add this import
import os
import itertools
from collections import defaultdict
from collections import Counter
from io import BytesIO
from PIL import Image

# CONFIGURATION
# Your Zoho API Credentials
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"


def get_zoho_access_token():
    print("Fetching Zoho access token...")
    resp = requests.post("https://accounts.zoho.com/oauth/v2/token", data={
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    data = resp.json()
    if "access_token" in data:
        print("✅ Access token retrieved")
        return data["access_token"]
    print(f"❌ Failed to get access token: {data}")
    raise Exception(f"Failed to get access token: {data}")


def check_skus_exist(access_token, skus_to_check):
    existing_skus = []
    url = "https://commerce.zoho.com/store/api/v1/products"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    params = {
        "per_page": 200,
        "page": 1,
        "organization_id": ORG_ID  # ✅ Correct parameter for Zoho Commerce
    }

    skus_to_check_upper = set(sku.upper() for sku in skus_to_check)

    while True:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            # Handle error 6024 (multiple orgs) specially
            try:
                data = resp.json()
                if data.get("code") == 6024:
                    print(f"❌ Error; Failed to fetch products from Zoho Commerce: {data.get('message')}")
                    print("User belongs to multiple organizations:")
                    for org in data.get("error_info", []):
                        print(f" - {org.get('organization_id')}: {org.get('name')}")
                    choice = input("Do you want to quit and start afresh? (y/n): ").strip().lower()
                    if choice == "y":
                        print("Exiting. Please retry with correct org settings.")
                        sys.exit(1)
                    else:
                        print("Proceeding anyway without SKU check. Be cautious!")
                        return []  # Skip SKU existence check
                else:
                    print(f"❌ Failed to fetch products: {resp.text}")
                    break
            except Exception:
                print(f"❌ Unexpected error: {resp.text}")
                break

        data = resp.json()
        products = data.get("products", [])
        if not products:
            break

        for product in products:
            variants = product.get("variants", [])
            for variant in variants:
                sku = variant.get("sku", "").upper()
                if sku in skus_to_check_upper and sku not in (s.upper() for s in existing_skus):
                    existing_skus.append(variant.get("sku"))

        page_context = data.get("page_context", {})
        if page_context.get("has_more_page"):
            params["page"] += 1
        else:
            break

    return existing_skus


def get_sku_list(access_token):
    while True:
        mode = input("Choose SKU input mode:\n1 - Generate SKUs\n2 - Provide SKU list (comma separated)\nEnter choice (1 or 2): ").strip()
        if mode == "1":
            prefix = input("Enter prefix (e.g. AKASKU1): ").strip()
            item_name = input("Enter item name (e.g. IP): ").strip()
            try:
                start = int(input("Enter start number (e.g. 1): ").strip())
                end = int(input("Enter end number (e.g. 10): ").strip())
            except ValueError:
                print("❌ Invalid number input.")
                continue

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
                print("Invalid padding option. Please try again.")
                continue

        elif mode == "2":
            sku_raw = input("Enter SKUs separated by commas: ").strip()
            skus = [sku.strip().upper() for sku in sku_raw.split(",") if sku.strip()]
            if not skus:
                print("No SKUs entered. Please try again.")
                continue
        else:
            print("Invalid mode. Please try again.")
            continue

        # Now check with your real function
        existing = check_skus_exist(access_token, skus)
        if existing:
            print("⚠️ The following SKUs already exist in Zoho Commerce:")
            for s in existing:
                print(f" - {s}")
            choice = input("Do you want to (R)eplace these SKUs or (E)nter new SKUs? [R/E]: ").strip().upper()
            if choice == "R":
                print("Proceeding with replacement of existing SKUs.")
                return mode, skus
            else:
                print("Restarting SKU input...")
                continue
        else:
            print(f"✅ SKUs accepted: {skus}")
            return mode, skus
            
def prompt_item_type():
    print("Select Item Type:")
    print("1 - Simple Item")
    print("2 - Contains Variants")
    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice == "1":
            return "Simple Item"
        elif choice == "2":
            return "Contains Variants"
        else:
            print("Invalid choice. Please enter 1 or 2.")


def get_mandatory_input(prompt_text):
    """Helper function to get non-empty input from user."""
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print(f"❌ This field is required. Please enter a value.")


def upload_images_for_product(product_id, access_token, base_url):
    """
    Upload images to the parent product.
    Returns a list of uploaded image dicts: [{"id": ..., "document_id": ..., "url": ...}, ...]
    """
    uploaded_images = []

    while True:
        upload_img = input("Do you want to upload images? (y/n): ").strip().lower()
        if upload_img not in ("y", "n"):
            print("❌ Invalid choice. Please enter 'y' or 'n'.")
            continue
        if upload_img == "n":
            break

        image_inputs = input("Enter full path(s) or URL(s), separated by commas: ").strip()
        if not image_inputs:
            print("❌ No input provided. Please try again.")
            continue

        image_list = [img.strip() for img in image_inputs.split(",") if img.strip()]
        if not image_list:
            print("❌ Invalid input format. Please try again.")
            continue

        for idx, image_input in enumerate(image_list, start=1):
            print(f"\n=== Uploading image {idx} of {len(image_list)}: {image_input} ===")
            try:
                # Open from URL or local path
                if image_input.startswith(("http://", "https://")):
                    resp = requests.get(image_input, stream=True, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                elif os.path.exists(image_input):
                    img = Image.open(image_input).convert("RGB")
                else:
                    print(f"❌ Skipped. Invalid path or URL: {image_input}")
                    continue

                # Convert → WebP optimized
                buffer = BytesIO()
                img.save(buffer, format="WEBP", quality=85, method=6)
                buffer.seek(0)
                files = {"image": ("optimized.webp", buffer, "image/webp")}

                # Upload to Zoho (product-level)
                res = requests.post(
                    f"{base_url}/products/{product_id}/images?organization_id={ORG_ID}",
                    files=files,
                    headers={
                        "Authorization": f"Zoho-oauthtoken {access_token}",
                        "X-com-zoho-commerce-organizationid": ORG_ID,
                    },
                )

                if res.status_code in (200, 201):
                    data = res.json()

                    # Normalize response
                    img_obj = None
                    if isinstance(data.get("data"), list) and data["data"]:
                        img_obj = data["data"][0]
                    elif "image" in data:
                        img_obj = data["image"]
                    elif isinstance(data.get("images"), list) and data["images"]:
                        img_obj = data["images"][0]
                    else:
                        img_obj = {}

                    zoho_image_id = (
                        img_obj.get("document_id") or  # preferred
                        img_obj.get("image_id") or     # fallback
                        img_obj.get("id")              # last resort
                    )
                    zoho_document_id = img_obj.get("document_id") or zoho_image_id
                    zoho_url = img_obj.get("image_url") or img_obj.get("url")

                    if zoho_image_id:
                        uploaded_images.append({
                            "id": zoho_image_id,                 # always populated
                            "document_id": zoho_document_id,     # safe fallback
                            "url": zoho_url                      # may be None
                        })
                        print(f"✅Optimised  Uploaded → Zoho ID: {zoho_image_id}, URL: {zoho_url or '[no URL returned]'}")
                    else:
                        print(f"⚠️ Upload succeeded but no usable ID found. Full response: {data}")
                else:
                    print(f"❌ Upload failed: {res.status_code} {res.text}")

            except Exception as e:
                print(f"❌ Error uploading {image_input}: {e}")

    return uploaded_images



def handle_product_and_variant_images(product_id, variants, access_token, base_url):
    """
    Upload product images, then assign them to variants in order.

    Rules:
    - Must upload (variant_count + 1) images minimum.
    - 1st image → Parent product.
    - Remaining images → Assigned in order → Variant1, Variant2, etc.
    - User cannot skip until all required images are uploaded.
    """
    variant_count = len(variants)
    print("\n=== Product Image Upload ===")
    print(f"You have {variant_count} variants. You MUST upload at least {variant_count + 1} images.")
    print("1st image will be used for parent product.")
    print("Remaining images will be mapped in order → Variant1, Variant2, etc.\n")

    # ✅ Force at least 1 image for parent
    uploaded_images = []
    while not uploaded_images:
        uploaded_images = upload_images_for_product(product_id, access_token, base_url)
        if not uploaded_images:
            print("❌ You must upload at least 1 parent image. Try again.")

    # ✅ Always take the first as parent image
    parent_image = uploaded_images[0]
    parent_doc_id = parent_image.get("document_id") or parent_image["id"]
    print(f"✅ Parent image uploaded (document_id {parent_doc_id})")

    # Ask if parent image should be used for all variants
    use_parent = input("Do you want to use the parent image for ALL variants? (y/n): ").strip().lower()

    mapping_summary = []

    if use_parent == "y":
        # Assign parent image to all variants
        for variant in variants:
            variant_id = variant.get("variant_id") or variant.get("id") or variant.get("item_id")
            if not variant_id:
                print(f"❌ No valid ID found for variant {variant.get('name')} (SKU {variant.get('sku')})")
                continue
            payload = {"document_ids": [parent_doc_id]}
            res = requests.put(
                f"{base_url}/variants/{variant_id}?organization_id={ORG_ID}",
                json=payload,
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "X-com-zoho-commerce-organizationid": ORG_ID,
                    "Content-Type": "application/json",
                },
            )
            if res.status_code in (200, 201):
                print(f"✅ {variant['name']} (SKU {variant['sku']}) ← parent image document_id {parent_doc_id}")
                mapping_summary.append((variant["name"], variant["sku"], parent_doc_id))
            else:
                print(f"❌ Failed to assign to {variant['name']} (SKU {variant['sku']}): {res.status_code} {res.text}")

    else:
        # ✅ Force complete upload of all variant images
        while len(uploaded_images) < variant_count + 1:
            print(f"⚠️ You have uploaded {len(uploaded_images)} images. "
                  f"You MUST upload {variant_count + 1} images total (1 parent + {variant_count} variants).")
            more_images = upload_images_for_product(product_id, access_token, base_url)
            if not more_images:
                print("❌ You must continue uploading until all required images are provided.")
                continue
            uploaded_images.extend(more_images)

        # ✅ Assign images (start from 2nd, skip parent)
        for idx, variant in enumerate(variants, start=1):
            image = uploaded_images[idx]
            doc_id = image.get("document_id") or image["id"]
            payload = {"document_ids": [doc_id]}

            variant_id = variant.get("variant_id") or variant.get("id") or variant.get("item_id")
            if not variant_id:
                print(f"❌ No valid ID found for variant {variant.get('name')} (SKU {variant.get('sku')})")
                continue

            print(f"→ Assigning image document_id {doc_id} to variant {variant['name']} (SKU {variant['sku']})")

            res = requests.put(
                f"{base_url}/variants/{variant_id}?organization_id={ORG_ID}",
                json=payload,
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                    "X-com-zoho-commerce-organizationid": ORG_ID,
                    "Content-Type": "application/json",
                },
            )
            if res.status_code in (200, 201):
                print(f"✅ {variant['name']} (SKU {variant['sku']}) ← image document_id {doc_id}")
                mapping_summary.append((variant["name"], variant["sku"], doc_id))
            else:
                print(f"❌ Failed to assign to {variant['name']} (SKU {variant['sku']}): {res.status_code} {res.text}")

    # ✅ Final Summary
    print("\n=== Final Mapping Summary ===")
    if mapping_summary:
        for name, sku, doc in mapping_summary:
            print(f"Variant {name} (SKU {sku}) ← document_id {doc}")
    else:
        print("⚠️ No variant images assigned.")


def prompt_attributes():
    attributes = {}
    while True:
        attr_name = input("Enter attribute name (or press Enter to finish): ").strip()
        if not attr_name:
            break
        values = input(f"Enter values for '{attr_name}' separated by commas: ").strip()
        values_list = [v.strip() for v in values.split(",") if v.strip()]
        if values_list:
            attributes[attr_name] = values_list
    return attributes

def get_category_id_from_name(access_token, org_id, category_name):
    url = f"https://commerce.zoho.com/store/api/v1/categories?organization_id={org_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": org_id,
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch categories: {response.status_code} {response.text}")
        return None

    data = response.json()
    categories = data.get("categories", [])

    # Build mapping of category_id -> category object
    cat_id_map = {cat["category_id"]: cat for cat in categories}


    def build_full_path(cat_id):
        cat = cat_id_map.get(cat_id)
        if not cat:
            return ""
        parent_id = cat.get("parent_id")
        if parent_id and parent_id in cat_id_map:
            return build_full_path(parent_id) + " > " + cat["name"]
        else:
            return cat["name"]

    # Build mapping of full path -> category_id
    full_path_map = {}
    for cat in categories:
        full_path = build_full_path(cat["category_id"])
        full_path_map[full_path.lower()] = cat["category_id"]

    # Try to match user input (case-insensitive)
    category_name_lower = category_name.strip().lower()
    if category_name_lower in full_path_map:
        return full_path_map[category_name_lower]
    else:
        print(f"❌ Category '{category_name}' does not exist. Please provide a valid category name.")
        print("Available categories:")
        for path in sorted(full_path_map.keys()):
            print(f" - {path}")
        return None

def get_all_brands(access_token, org_id):
    """
    Fetch all brands from Zoho Commerce and return a dictionary
    mapping brand name -> brand_id
    """
    import requests

    url = f"https://commerce.zoho.com/store/api/v1/brands?organization_id={org_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": org_id,
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


def calculate_variants(attributes):
    if not attributes:
        return 1, [()]
    all_combos = list(itertools.product(*attributes.values()))
    return len(all_combos), all_combos


def prompt_seo_and_description(title):
    # Prompt for SEO keywords, combine with title words
    user_keywords = input(f"Enter SEO keywords for '{title}' (comma separated): ").strip()
    title_keywords = [kw.strip() for kw in title.split() if kw.strip()]
    user_keywords_list = [kw.strip() for kw in user_keywords.split(",") if kw.strip()]
    combined_keywords = list(dict.fromkeys(title_keywords + user_keywords_list))
    combined_seo_keywords = ", ".join(combined_keywords)
    return combined_seo_keywords


def create_item_simulation(item_data):
    print("\n=== Final item data ===")
    print(json.dumps(item_data, indent=2))
    confirm = input("Create item with above data? (y/n): ").strip().lower()
    if confirm == 'y':
        print("Creating item... (API call not implemented)")
        # Implement the actual API call here to create the item in Zoho Inventory
    else:
        print("Item creation cancelled.")

def build_product_attributes_from_variants(variant_combos):
    """
    Given a list of variant attribute tuples, e.g.
    [("Rom 64GB", "Red"), ("Rom 64GB", "Green"), ("RoM 39GB", "Red"), ("RoM 39GB", "Green")],
    build a list of product-level attributes with name, type, options.
    """
    options_per_attr = defaultdict(set)
    for combo in variant_combos:
        for idx, val in enumerate(combo):
            options_per_attr[idx].add(val)

    product_attributes = []
    for idx in range(len(options_per_attr)):
        attr_name = f"Attribute{idx+1}"
        options = sorted(list(options_per_attr[idx]))
        attr_obj = {
            "name": attr_name,
            "type": "select",   # or "colour" if you want to customize attribute type
            "options": options
        }
        product_attributes.append(attr_obj)

    return product_attributes

def prepare_variants(item_data, variant_combos, skus):
    product_attributes = item_data.get("attributes", [])
    
    # Defensive fix: Ensure product_attributes is a list of dicts with 'name'
    if not isinstance(product_attributes, list) or not all(isinstance(attr, dict) for attr in product_attributes):
        print("Warning: 'attributes' is not a list of dicts. Setting empty attributes.")
        product_attributes = []
    
    item_data["variants"] = []
    variant_count = len(variant_combos)

    if variant_count > 1:
        for i, combo in enumerate(variant_combos):
            attr_values = {}
            for idx, val in enumerate(combo):
                if idx < len(product_attributes) and "name" in product_attributes[idx]:
                    attr_key = product_attributes[idx]["name"]
                else:
                    attr_key = f"Attribute{idx+1}"
                attr_values[attr_key] = val

            sku = skus[i] if i < len(skus) else ""

            # Build readable attribute string like "Color: Red, Size: M"
            attr_display = ", ".join([f"{k}: {v}" for k, v in attr_values.items()])
            display_name = f"{item_data['title']} - {attr_display} (SKU: {sku})" if attr_display else f"{item_data['title']} (SKU: {sku})"

            while True:
                try:
                    rate = float(input(f"Enter selling price for {display_name}: "))
                    break
                except ValueError:
                    print("Invalid price. Please enter a numeric value.")

            attr_str = "-".join(attr_values.values()) if attr_values else sku
            variant_name = f"{item_data['title']}-{attr_str}" if attr_str else item_data["title"]

            item_data["variants"].append({
                "attributes": attr_values,
                "sku": sku,
                "rate": rate,
                "name": variant_name
            })
    else:
        sku = skus[0] if skus else ""

        single_variant_attrs = {}
        for attr in product_attributes:
            options = attr.get("options", [])
            attr_name = attr.get("name", "Attribute1")
            single_variant_attrs[attr_name] = options[0] if options else "Default"

        # Build readable display name
        attr_display = ", ".join([f"{k}: {v}" for k, v in single_variant_attrs.items()])
        display_name = f"{item_data['title']} - {attr_display} (SKU: {sku})" if attr_display else f"{item_data['title']} (SKU: {sku})"

        while True:
            try:
                rate = float(input(f"Enter selling price for {display_name}: "))
                break
            except ValueError:
                print("Invalid price. Please enter a numeric value.")

        item_data["variants"].append({
            "attributes": single_variant_attrs,
            "sku": sku,
            "rate": rate,
            "name": sku or item_data["title"]
        })

    print("\nVariants to be sent:")
    for v in item_data["variants"]:
        print(v)


   #fixing attribute
def fix_attributes_format(item_data):
    attributes = item_data.get("attributes", {})
    if isinstance(attributes, dict):
        # Convert dict of lists to list of dicts
        item_data["attributes"] = [
            {"name": key, "options": value} for key, value in attributes.items()
        ]


def create_item_zoho_commerce(item_data, access_token, log_filename='log.xlsx'):

    base_url = "https://commerce.zoho.com/store/api/v1"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-commerce-organizationid": ORG_ID,
        "Content-Type": "application/json"
    }

    # --- Build Product Payload ---
    product_payload = {
        "name": item_data["title"],
        "url": slugify(item_data["title"]),
        "product_short_description": item_data["item_description_plain"],
        "product_description": item_data["product_description_html"],
        "category_id": item_data["category"],
        "brand": item_data["brand"],
        "seo_title": item_data.get("seo_title"),
        "seo_keyword": item_data.get("seo_keywords", ""),
        "seo_description": item_data.get("seo_description", item_data["item_description_plain"]),
        "unit": item_data["unit"],
        "company_id": ORG_ID,
        "variant_type": "inventory",   # Required for products with variants
        "variants": []
    }

    # --- Map Attributes to Zoho's flat structure ---
    attributes = item_data.get("attributes", [])
    for idx, attr in enumerate(attributes[:3], start=1):  # Zoho allows up to 3 attributes
        product_payload[f"attribute_name{idx}"] = attr.get("name")
        product_payload[f"attribute_type{idx}"] = attr.get("type", "text")

    # --- Add Variants ---
    for v in item_data.get("variants", []):
        variant_payload = {
            "sku": v.get("sku", ""),
            "rate": v.get("rate", 0),
            "name": v.get("name", v.get("sku", "")),
        }

        # Map each attribute's value for this variant
        for idx, attr in enumerate(attributes[:3], start=1):
            key = f"attribute_option_name{idx}"
            variant_payload[key] = v.get("attributes", {}).get(attr.get("name"))

        product_payload["variants"].append(variant_payload)

    # --- API Call ---
    print("\n=== Creating product with variants ===")
    res = requests.post(f"{base_url}/products?organization_id={ORG_ID}",
                        json=product_payload,
                        headers=headers)

    if res.status_code not in (200, 201):
        print(f"❌ Failed to create product: {res.status_code} {res.text}")

    created_product = res.json().get("product", {})
    product_id = created_product.get("product_id")

    print(f"✅ Product created successfully with attributes!")
    print(f"Product ID: {product_id}")
    print(f"Name: {created_product.get('name')}")
    print(f"Category ID: {created_product.get('category_id')}")
    print(f"Brand: {created_product.get('brand')}")
    print(f"Unit: {created_product.get('unit')}")
    print(f"SEO Title: {created_product.get('seo_title')}")
    print(f"SEO Keywords: {created_product.get('seo_keywords',item_data.get("seo_keywords", ""))}")
    print(f"SEO Description: {created_product.get('seo_description')}")
    print("=================================\n")
# 🔄 New Step: Handle parent + variant images
    handle_product_and_variant_images(
        product_id,
        created_product.get("variants", []),  # ✅ pass variants list only
        access_token,
        base_url
    )
   

    
    # --- Logging to Excel ---
    log_entries = [{
        "Type": "Product",
        "Product ID": product_id,
        "SKU": "",
        "Name": created_product.get("name", ""),
        "Price": "",
        "Attributes": json.dumps(attributes),
        "Status": "Created"
    }]

    for v in created_product.get("variants", []):
        log_entries.append({
            "Type": "Variant",
            "Product ID": product_id,
            "SKU": v.get("sku", ""),
            "Name": v.get("name", ""),
            "Price": v.get("rate", ""),
            "Attributes": json.dumps(v.get("attributes", {})),
            "Status": "Created"
        })

    df_log = pd.DataFrame(log_entries)

    if os.path.exists(log_filename):
        existing_df = pd.read_excel(log_filename)
        df_log = pd.concat([existing_df, df_log], ignore_index=True)

    df_log.to_excel(log_filename, index=False)
    print(f"\n✅ Log saved to {log_filename}")

    return product_id

def main():
    print("### Item Creation Script ###")
    payload = {}  # Create it first
    access_token = get_zoho_access_token()
    while True:
        ##Ca
        category_id = None
        while not category_id:
           category = input("Enter Category: ").strip()
           category_id = get_category_id_from_name(access_token, ORG_ID, category)  # This should fetch category ID from Zoho Commerce
            
           if category_id:
                payload["category_id"] = category_id
                print(f"✅ Category '{category}' matched with ID: {category_id}")
            
           else:
                print(f"❌ Category '{category}' not found. Please try again.")

        
        # brand = input("Enter Brand: ").strip()
        brand_valid = False
        while not brand_valid:
            brand = input("Enter Brand: ").strip()
            
            # Fetch existing brands
            existing_brands = get_all_brands(access_token, ORG_ID)
            if not existing_brands:
                print("❌ No brands found in your store. Please create brands first in Zoho Commerce.")
                break
        
            # Normalize for comparison
            normalized_map = {k.lower(): v for k, v in existing_brands.items()}
            if brand.lower() in normalized_map:
                payload["brand"] = normalized_map[brand.lower()]  # store brand_id
                print(f"✅ Brand '{brand}' is valid and ID stored in payload.")
                brand_valid = True
            else:
                print(f"❌ Brand '{brand}' not found. Please choose from the following available brands:")
                for idx, brand in enumerate(existing_brands.keys(), 1):
                    print(f"{idx}. {brand}")
                print("Please re-enter a valid brand.")
        
        unit = get_mandatory_input("Enter Unit (e.g. pcs, kg): ")
    
        item_type = prompt_item_type()
    
        item_title = get_mandatory_input("Enter Item Title: ")

        #..................Multiple input for item dec and product desc. 
        #to start a new line type \n on a multiple words for pasting or press enter
        #Press enter to start a new line when typing. Pree enter to start new when typing.
        def get_multiline_input_with_marker(prompt, marker="\\n"):
            """
            Capture multi-line input where the user can type a marker (default: \n)
            to indicate a line break. Preserves formatting exactly otherwise.
            Input ends when the user presses Enter on an empty line.
            Returns:
                - formatted_html: string with <br> for Zoho product description
                - plain_text: string as-is for SEO description
            """
            print(f"{prompt}\n(Type '{marker}' wherever you want a line break, press Enter on empty line to finish)")
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break  # Allows Ctrl+D / Ctrl+Z to end input in terminal
                if line == "":
                    break  # Empty line ends input
                lines.append(line)
            
            # Join lines with spaces first, then replace marker with actual line breaks
            value = " ".join(lines).replace(marker, "\n").rstrip()
            
            if not value.strip():
                print("⚠️ Input cannot be empty. Please enter again.")
                return get_multiline_input_with_marker(prompt, marker)
            
            # HTML version for product description
            formatted_html = value.replace("\n", "<br>")
        
            # Plain text version for SEO
            plain_text = value
            
            return formatted_html, plain_text
        
        
        # ================= Usage =================
        item_desc_html, item_desc_plain = get_multiline_input_with_marker("Enter Item Description:")
        product_desc_html, product_desc_plain = get_multiline_input_with_marker("Enter Product Description:")
        
        print("\n=== Captured Item Description (HTML) ===")
        print(item_desc_html)
        print("\n=== Captured Item Description (Plain Text for SEO) ===")
        print(item_desc_plain)
        
        print("\n=== Captured Product Description (HTML) ===")
        print(product_desc_html)
        print("\n=== Captured Product Description (Plain Text for SEO) ===")
        print(product_desc_plain)

        # -----------------------------------------------------------------

        attributes = {}
        variant_count = 1
        variant_combos = [()]
    
        if item_type == "Contains Variants":
            attributes = prompt_attributes()
            variant_count, variant_combos = calculate_variants(attributes)
            print(f"Total variants to be created: {variant_count}")


        unused_skus = []
        # SKU input & validation loop
        while True:
            mode, skus = get_sku_list(access_token)

            if variant_count > 1:
                if len(skus) < variant_count:
                    print(f"⚠️ Number of SKUs ({len(skus)}) is LESS than number of variants ({variant_count}). Please regenerate SKUs.")
                    continue  # ask again
                elif len(skus) > variant_count:
                    print(f"⚠️ Number of SKUs ({len(skus)}) is MORE than number of variants ({variant_count}). Will use only the first {variant_count} SKUs.")
                    unused_skus = skus[variant_count:]
                    skus = skus[:variant_count]
            else:
                # Single variant case
                if len(skus) != 1:
                    print("⚠️ For single variant you must provide exactly one SKU. Please regenerate SKUs.")
                    continue

            # Check for existing SKUs
            existing_skus = check_skus_exist(access_token, skus)
            if existing_skus:
                print(f"❌ The following SKUs already exist in the store: {existing_skus}")
                print("Please regenerate SKUs.")
                continue  # re-ask SKU list

            # If we reach here, SKUs are valid and unique
            break

        print(f"✅ SKUs are unique. Proceeding with item creation for '{item_title}' ({item_type})")

        seo_title = item_title
        seo_keywords = prompt_seo_and_description(item_title)

        mode_choice = None
        while mode_choice not in ("1", "2"):
            mode_choice = input("Choose mode:\n1 - Create the item\n2 - Edit item sections\nEnter choice (1 or 2): ").strip()

        item_data = {
            "category": category_id,
            "brand": brand,
            "unit": unit,
            "item_type": item_type,
            "title": item_title,
            "item_description_plain": item_desc_plain,
            "product_description_html": product_desc_html,
                    # "image": image_path,
            "attributes": attributes,
            "variants": [],
            "seo_title": seo_title,
            "seo_keywords": seo_keywords
        }

        def edit_sections():
            nonlocal item_data
            while True:
                print("\nWhat do you want to edit?")
                print("1 - Category")
                print("2 - Brand")
                print("3 - Unit")
                print("4 - Item Type")
                print("5 - Item Title")
                print("6 - Item Description")
                print("7 - Product Description")
                print("8 - Attributes, Variants and SKU")
                print("9 - SEO Keywords")
                print("0 - Done editing")
                choice = input("Enter choice: ").strip()
                
                if choice == "0":
                    break
                elif choice == "1":
                    while True:
                        val = input("Enter new Category (press Enter to skip): ").strip()
                        if not val:
                            break  # skip editing
                        category_id = get_category_id_from_name(access_token, ORG_ID, val)
                        if category_id:
                            item_data["category"] = val
                            item_data["category_id"] = category_id
                            print(f"✅ Category '{val}' matched with ID: {category_id}")
                            break
                        else:
                            print(f"❌ Category '{val}' not found. Please try again.")
                
                elif choice == "2":
                    while True:
                        val = input("Enter new Brand (press Enter to skip): ").strip()
                        if not val:
                            break  # skip editing
                        existing_brands = get_all_brands(access_token, ORG_ID)
                        if not existing_brands:
                            print("❌ No brands found in your store. Please create brands first in Zoho Commerce.")
                            break
                        normalized_map = {k.lower(): v for k, v in existing_brands.items()}
                        if val.lower() in normalized_map:
                            item_data["brand"] = val
                            item_data["brand_id"] = normalized_map[val.lower()]
                            print(f"✅ Brand '{val}' is valid and ID stored.")
                            break
                        else:
                            print(f"❌ Brand '{val}' not found. Available brands are:")
                            for idx, brand_name in enumerate(existing_brands.keys(), 1):
                                print(f"{idx}. {brand_name}")
                            print("Please re-enter a valid brand.")

                                
                elif choice == "3":
                    val = input("Enter new Unit (press Enter to skip): ").strip()
                    if val:
                        item_data["unit"] = val
                elif choice == "4":
                    new_type = prompt_item_type()
                    if new_type:
                        item_data["item_type"] = new_type
                elif choice == "5":
                    val = input("Enter new Item Title (press Enter to skip): ").strip()
                    if val:
                        item_data["title"] = val
                
                elif choice == "6":
                    print("Updating Item Description...")
                    # After capturing input
                    val_html, val_plain = get_multiline_input_with_marker("Enter Item Description:")
                    item_data["item_description_html"] = val_html
                    item_data["item_description_plain"] = val_plain
                    item_data["item_description"] = val_plain  # <-- for Zoho payload
                    print("✅ Item Description updated.")
                
                elif choice == "7":
                    print("Updating Product Description...")
                    val_html, val_plain = get_multiline_input_with_marker("Enter Product Description:")
                    item_data["product_description_html"] = val_html
                    item_data["product_description_plain"] = val_plain
                    item_data["product_description"] = val_html  # <-- for Zoho payload 
                    print("✅ Product Description updated.")

                elif choice == "8":
                    print("⚠️ You can only start afresh for Attributes, Variants, and SKUs.")
                    yn = input("Do you want to start afresh? (y/N): ").strip().lower()
                    if yn == "y":
                        print("🔄 Restarting the main function to start afresh...")
                        main()  # Call main() to start fresh
                        return  # Exit edit_sections and go to "Create another item?"
                    else:
                        print("↩️ Skipping attributes/variants/SKUs.")
                        return  # Exit edit_sections and go to "Create another item?"

                elif choice == "9":
                    val = prompt_seo_and_description(item_data["title"])
                    if val:
                        item_data["seo_keywords"] = val
        
                else:
                    print("Invalid choice.")
        
        if mode_choice == "2":
            edit_sections()
            
        fix_attributes_format(item_data)  # <- Fix attributes structure here
        print("Attributes before preparing variants:", item_data.get("attributes"))
        # Prepare the variants (asks for rates, builds variants list)
        prepare_variants(item_data, variant_combos, skus)
        # Now create the product on Zoho Commerce
        create_item_zoho_commerce(item_data, access_token)

        # Uncomment below to create item on Zoho Commerce live
        # create_item_zoho_commerce(item_data, access_token)

        print("Item creation process completed.")

        cont = input("Create another item? (y/n): ").strip().lower()
        if cont != "y":
            print("✅ Access token retrieved")
            print("Exiting.")
            break

if __name__ == "__main__":
    main()
