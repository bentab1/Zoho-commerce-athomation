import os
import requests
from io import BytesIO
from PIL import Image
import time
import openpyxl
import sys, time, select
import threading

# ================= CONFIG ================= #
ZOHO_CLIENT_ID = "1000.S0MCEJ7YY6TVO6HC3RED00QLK7KDRA"
ZOHO_CLIENT_SECRET = "1bbb7b39b57c784a38cbdc9c6e82496ee690bde86d"
ZOHO_REFRESH_TOKEN = "1000.e6b8fed22697a4847fa2912eb7bcdc71.db25a2b68ef38e7bf01858ad17489870"
ORG_ID = "891730368"
BASE_URL = "https://commerce.zoho.com/store/api/v1"

# ================= AUTH ================= #
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
    raise Exception(f"❌ Failed to get access token: {data}")

# -------------------- PRODUCT FETCH --------------------
def fetch_all_products(access_token, base_url):
    products = []
    page = 1
    while True:
        res = requests.get(
            f"{base_url}/products?page={page}&per_page=200&organization_id={ORG_ID}",
            headers={
                "Authorization": f"Zoho-oauthtoken {access_token}",
                "X-com-zoho-commerce-organizationid": ORG_ID,
            },
        )
        if res.status_code != 200:
            print(f"❌ Failed to fetch products: {res.status_code} {res.text}")
            break
        data = res.json().get("products", [])
        if not data:
            break
        products.extend(data)
        page += 1
    return products

# -------------------- IMAGE UPLOAD --------------------
def upload_images_for_product(product_id, access_token, base_url):
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
        for idx, image_input in enumerate(image_list, start=1):
            print(f"\n=== Uploading image {idx} of {len(image_list)}: {image_input} ===")
            try:
                if image_input.startswith(("http://", "https://")):
                    resp = requests.get(image_input, stream=True, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                elif os.path.exists(image_input):
                    img = Image.open(image_input).convert("RGB")
                else:
                    print(f"❌ Skipped. Invalid path or URL: {image_input}")
                    continue

                buffer = BytesIO()
                img.save(buffer, format="WEBP", quality=85, method=6)
                buffer.seek(0)
                files = {"image": ("optimized.webp", buffer, "image/webp")}

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
                    img_obj = (data.get("data") or [{}])[0] if isinstance(data.get("data"), list) else data.get("image") or {}
                    zoho_image_id = img_obj.get("document_id") or img_obj.get("image_id") or img_obj.get("id")
                    zoho_document_id = img_obj.get("document_id") or zoho_image_id
                    zoho_url = img_obj.get("image_url") or img_obj.get("url")
                    if zoho_image_id:
                        uploaded_images.append({"id": zoho_image_id, "document_id": zoho_document_id, "url": zoho_url})
                        print(f"✅ Uploaded → Zoho ID: {zoho_image_id}, URL: {zoho_url or '[no URL returned]'}")
                    else:
                        print(f"⚠️ Upload succeeded but no usable ID found. Full response: {data}")
                else:
                    print(f"❌ Upload failed: {res.status_code} {res.text}")

            except Exception as e:
                print(f"❌ Error uploading {image_input}: {e}")

    return uploaded_images

# -------------------- IMAGE DELETE --------------------
def delete_product_image(product_or_variant_id, doc_id, access_token, base_url, is_variant=False):
    if not doc_id:
        print("⚠️ No document_id provided for deletion.")
        return False
    url = f"{base_url}/variants/{product_or_variant_id}/documents/{doc_id}?organization_id={ORG_ID}" if is_variant else f"{base_url}/products/{product_or_variant_id}/documents/{doc_id}?organization_id={ORG_ID}"
    res = requests.delete(url, headers={"Authorization": f"Zoho-oauthtoken {access_token}", "X-com-zoho-commerce-organizationid": ORG_ID})
    if res.status_code in (200, 204):
        target = "Variant" if is_variant else "Product"
        print(f"🗑️ Deleted image {doc_id} from {target} {product_or_variant_id}")
        return True
    else:
        print(f"❌ Failed to delete image {doc_id}: {res.status_code} {res.text}")
        return False

# -------------------- IMAGE SLOT RESOLUTION --------------------
def resolve_image_for_slot(slot_name, product_id, access_token, base_url, existing_images, required_count, slot_index):
    while True:
        upload_choice = input(f"Do you want to upload a new image for {slot_name}? (y/n): ").strip().lower()
        if upload_choice == "y":
            uploads = upload_images_for_product(product_id, access_token, base_url)
            if uploads:
                new_img = uploads[0]
                if slot_index < len(existing_images):
                    existing_images[slot_index] = new_img
                else:
                    while len(existing_images) < slot_index:
                        existing_images.append(None)
                    existing_images.append(new_img)
                return new_img
            print("⚠️ No images uploaded. Try again.")
        elif upload_choice == "n":
            if len(existing_images) > required_count:
                print(f"\n⚠️ Choose an existing spare image for {slot_name}:")
                for j, im in enumerate(existing_images, start=1):
                    print(f" {j}. document_id={im['document_id']} url={im['url']}")
                sel = input("👉 Enter image number: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(existing_images):
                    chosen = existing_images[int(sel) - 1]
                    existing_images[slot_index] = chosen
                    return chosen
                print("⚠️ Invalid choice. Try again.")
            else:
                print("⚠️ Not enough spare images. You must upload one.")
        else:
            print("⚠️ Invalid input. Type 'y' or 'n'.")

# -------------------- MAIN IMAGE HANDLER --------------------
def handle_product_and_variant_images(product, access_token, base_url):
    product_id = product["product_id"]
    product_name = product["name"]
    variants = product.get("variants", []) or []
    variant_count = len(variants)
    required_count = variant_count + 1  # parent + variants

    print(f"\n=== Processing Product: {product_name} (ID: {product_id}) ===")
    print(f"→ {variant_count} variants found → need {required_count} total images.")

    # Fetch product details
    res = requests.get(f"{base_url}/products/{product_id}?organization_id={ORG_ID}",
                       headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                "X-com-zoho-commerce-organizationid": ORG_ID})
    if res.status_code != 200:
        print(f"❌ Failed to fetch product: {res.status_code} {res.text}")
        return

    product_data = res.json().get("product", {}) or {}
    existing_images_raw = product_data.get("documents", [])
    existing_images = [{"document_id": im.get("document_id") or im.get("id"),
                        "url": im.get("image_url") or im.get("url")} 
                       for im in existing_images_raw if (im.get("document_id") or im.get("id"))]

    print(f"\n=== Images Found ({len(existing_images)} image(s)) ===")
    for i, im in enumerate(existing_images, start=1):
        print(f"  {i}. document_id={im['document_id']} url={im['url']}")

    print("\n=== Image Options ===")
    print("1 → Overwrite only parent image")
    print("2 → Overwrite ALL variant images")
    print("3 → Overwrite EVERYTHING (parent + variants)")
    print("4 → Keep all existing images")
    print("5 → Overwrite specific variant(s)")
    print("6 → Delete specific image(s)")
    print("7 → Upload new image without replacing")  # ✅ New option
    choice = input("👉 Choose an option (or press Enter to quit): ").strip()
    if not choice:
        print("⏹ Exiting (user quit).")
        return

    # CASE 6: Delete images
    if choice == "6":
        if not existing_images:
            print("⚠️ No images to delete.")
        else:
            for i, im in enumerate(existing_images, start=1):
                print(f" {i}. document_id={im['document_id']} url={im['url']}")
            sel = input("Enter image number(s) to delete, comma-separated: ").strip()
            nums = [int(x) for x in sel.split(",") if x.strip().isdigit()]
            deleted_count = 0
            for n in nums:
                if 1 <= n <= len(existing_images):
                    if delete_product_image(product_id, existing_images[n-1]["document_id"], access_token, base_url):
                        existing_images[n-1] = None
                        deleted_count += 1
            existing_images = [im for im in existing_images if im]
            print(f"✅ {deleted_count} image(s) deleted.")
        return

    # CASE 7: Upload new images without replacing
    if choice == "7":
        uploads = upload_images_for_product(product_id, access_token, base_url)
        if uploads:
            existing_images.extend(uploads)
            for img in uploads:
                print(f"✅ Uploaded and added: document_id={img['document_id']} url={img['url']}")
        else:
            print("⚠️ No images uploaded.")
        return

    # CASES 1–5: Overwrite logic
    changed_positions = []
    if choice == "1":
        if existing_images:
            delete_product_image(product_id, existing_images[0]["document_id"], access_token, base_url)
        resolve_image_for_slot("Parent Product", product_id, access_token, base_url, existing_images, required_count, 0)
        changed_positions = [0]

    elif choice == "2":
        for idx in range(1, required_count):
            if idx < len(existing_images):
                delete_product_image(product_id, existing_images[idx]["document_id"], access_token, base_url)
            resolve_image_for_slot(f"Variant {idx}", product_id, access_token, base_url, existing_images, required_count, idx)
            changed_positions.append(idx)

    elif choice == "3":
        for im in existing_images:
            delete_product_image(product_id, im["document_id"], access_token, base_url)
        existing_images.clear()
        for idx in range(required_count):
            resolve_image_for_slot("Parent" if idx == 0 else f"Variant {idx}", product_id, access_token, base_url, existing_images, required_count, idx)
            changed_positions.append(idx)

    elif choice == "4":
        if len(existing_images) < required_count:
            print(f"⚠️ Cannot keep images. Missing {required_count - len(existing_images)} more.")
            return

    elif choice == "5":
        variant_nums = input(f"👉 Enter variant numbers (1-{variant_count}) comma-separated: ").strip()
        nums = [int(x) for x in variant_nums.split(",") if x.strip().isdigit()]
        for vnum in nums:
            slot_index = vnum
            if slot_index < len(existing_images):
                delete_product_image(product_id, existing_images[slot_index]["document_id"], access_token, base_url)
            resolve_image_for_slot(f"Variant {vnum}", product_id, access_token, base_url, existing_images, required_count, slot_index)
            changed_positions.append(slot_index)

    # Fill any remaining slots
    while len(existing_images) < required_count:
        resolve_image_for_slot(f"Slot {len(existing_images)}", product_id, access_token, base_url, existing_images, required_count, len(existing_images))

    # Assign images to parent and variants
    print("\n✅ Assigning images to parent + variants...")
    mapping_summary = []

    if existing_images:
        doc_id = existing_images[0]["document_id"]
        payload_parent = {"document_ids": [doc_id]}
        res_parent = requests.put(f"{BASE_URL}/products/{product_id}?organization_id={ORG_ID}",
                                  json=payload_parent,
                                  headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                           "X-com-zoho-commerce-organizationid": ORG_ID,
                                           "Content-Type": "application/json"})
        if res_parent.status_code in (200, 201):
            print(f"✅ Parent product assigned image {doc_id}")
            mapping_summary.append(("Parent product", "—", doc_id))
        else:
            print(f"❌ Failed parent image assign: {res_parent.status_code} {res_parent.text}")

    for i, variant in enumerate(variants, start=1):
        if i >= len(existing_images):
            print(f"⚠️ Skipping variant {variant.get('sku')}: no image assigned")
            continue
        doc_id = existing_images[i]["document_id"]
        variant_id = variant.get("variant_id") or variant.get("id") or variant.get("item_id")
        payload = {"document_ids": [doc_id]}
        res_v = requests.put(f"{BASE_URL}/variants/{variant_id}?organization_id={ORG_ID}",
                             json=payload,
                             headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                      "X-com-zoho-commerce-organizationid": ORG_ID,
                                      "Content-Type": "application/json"})
        if res_v.status_code in (200, 201):
            print(f"✅ {variant.get('name')} (SKU {variant.get('sku')}) ← {doc_id}")
            mapping_summary.append((variant.get("name"), variant.get("sku"), doc_id))
        else:
            print(f"❌ Failed for {variant.get('sku')}: {res_v.status_code} {res_v.text}")

    print("\n=== Mapping Summary ===")
    for name, sku, doc in mapping_summary:
        print(f"{name} (SKU {sku}) ← {doc}")

#log to excel
def export_logs_to_excel(processed, unprocessed, filename="products_log.xlsx"):
    wb = openpyxl.Workbook()

    # Sheet 1: Processed
    ws1 = wb.active
    ws1.title = "Processed"
    ws1.append(["Product ID", "Product Name", "Variant ID", "Variant SKU", "Assigned Image ID"])
    for row in processed:
        ws1.append(row)

    # Sheet 2: Unprocessed
    ws2 = wb.create_sheet("Unprocessed")
    ws2.append(["Product ID", "Product Name", "Reason"])
    for row in unprocessed:
        ws2.append(row)

    wb.save(filename)
    print(f"\n✅ Logs exported to {filename}")


def main():
    access_token = get_zoho_access_token()
    products = fetch_all_products(access_token, BASE_URL)
    if not products:
        print("⚠️ No products found.")
        return

    processed_log = []
    unprocessed_log = []

    print("\n=== Product List ===")
    for idx, prod in enumerate(products, start=1):
        print(f"{idx}. {prod['name']} (ID: {prod['product_id']}, Variants: {len(prod.get('variants', []))})")

    print("\n=== Modes ===")
    print("1 → Manual (Process & Assign products images)")
    print("2 → Automatic (Process & Synch Products to Variants)")

    mode = input("👉 Choose a mode: ").strip()
    if mode == "1":
        selection = input("Enter product number(s) (e.g. 2,5) or 'all': ").strip()
        if not selection:
            print("❌ No selection made.")
            return
        indexes = list(range(1, len(products) + 1)) if selection.lower() == "all" else [int(i.strip()) for i in selection.split(",")]
        for idx in indexes:
            if idx < 1 or idx > len(products):
                print(f"⚠️ Skipping invalid product number {idx}")
                continue
            prod = products[idx - 1]
            handle_product_and_variant_images(prod, access_token, BASE_URL)

    elif mode == "2":
        prod_choice = input("Do you want to provide product numbers (comma-separated)? (y/n): ").strip().lower()
        if prod_choice == "y":
            selection = input("Enter product number(s), e.g. 2,5: ").strip()
            if not selection:
                print("❌ No selection made. Exiting.")
                return
            indexes = [int(i.strip()) for i in selection.split(",")]
        else:
            indexes = list(range(1, len(products) + 1))

        use_parent_for_all = input("Use parent image for all variants? (y/n): ").strip().lower() == "y"

        for idx in indexes:
            if idx < 1 or idx > len(products):
                print(f"⚠️ Skipping invalid product number {idx}")
                continue

            prod = products[idx - 1]
            product_id = prod["product_id"]
            product_name = prod["name"]
            print(f"\n=== Auto-processing product: {product_name} (ID: {product_id}) ===")

            # Fetch product details
            res = requests.get(f"{BASE_URL}/products/{product_id}?organization_id={ORG_ID}",
                               headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                        "X-com-zoho-commerce-organizationid": ORG_ID})
            if res.status_code != 200:
                print(f"❌ Failed to fetch product: {res.status_code} {res.text}")
                unprocessed_log.append([product_id, product_name, f"Fetch failed ({res.status_code})"])
                continue

            product_data = res.json().get("product", {}) or {}
            existing_images_raw = product_data.get("documents", [])
            existing_images = [{"document_id": im.get("document_id") or im.get("id"),
                                "url": im.get("image_url") or im.get("url")}
                               for im in existing_images_raw if (im.get("document_id") or im.get("id"))]
            # If no images exist at this point, skip safely
            if not existing_images:
                print(f"❌ No images available for product {product_name} (ID: {product_id}). Skipping...")
                unprocessed_log.append([product_id, product_name, "No images available"])
                continue

            parent_doc_id = existing_images[0]["document_id"]

            # Case 1: use parent image for all
            if use_parent_for_all and len(existing_images) >= 1:
                variants = prod.get("variants", []) or []
                for variant in variants:
                    variant_id = variant.get("variant_id") or variant.get("id") or variant.get("item_id")
                    sku = variant.get("sku")
                    payload = {"document_ids": [parent_doc_id]}
                    res_v = requests.put(f"{BASE_URL}/variants/{variant_id}?organization_id={ORG_ID}",
                                         json=payload,
                                         headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                                  "X-com-zoho-commerce-organizationid": ORG_ID,
                                                  "Content-Type": "application/json"})
                    if res_v.status_code in (200, 201):
                        print(f"✅ {variant.get('name')} (SKU {sku}) ← Parent image {parent_doc_id}")
                        processed_log.append([product_id, product_name, variant_id, sku, parent_doc_id])
                    else:
                        print(f"❌ Failed for {sku}: {res_v.status_code} {res_v.text}")
                        unprocessed_log.append([product_id, product_name, f"Variant {sku} assign failed"])

                # Assign parent to product
                payload_parent = {"document_ids": [parent_doc_id]}
                res_parent = requests.put(f"{BASE_URL}/products/{product_id}?organization_id={ORG_ID}",
                                          json=payload_parent,
                                          headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                                   "X-com-zoho-commerce-organizationid": ORG_ID,
                                                   "Content-Type": "application/json"})
                if res_parent.status_code in (200, 201):
                    print(f"✅ Parent product assigned image {parent_doc_id}")
                    processed_log.append([product_id, product_name, "PARENT", "-", parent_doc_id])
                else:
                    print(f"❌ Failed parent image assign: {res_parent.status_code} {res_parent.text}")
                    unprocessed_log.append([product_id, product_name, "Parent assign failed"])

            # Case 2: assign sequential images, fallback to parent
            else:
                variants = prod.get("variants", []) or []

                # Assign parent first
                payload_parent = {"document_ids": [parent_doc_id]}
                res_parent = requests.put(f"{BASE_URL}/products/{product_id}?organization_id={ORG_ID}",
                                          json=payload_parent,
                                          headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                                   "X-com-zoho-commerce-organizationid": ORG_ID,
                                                   "Content-Type": "application/json"})
                if res_parent.status_code in (200, 201):
                    print(f"✅ Parent product assigned image {parent_doc_id}")
                    processed_log.append([product_id, product_name, "PARENT", "-", parent_doc_id])
                else:
                    print(f"❌ Failed parent image assign: {res_parent.status_code} {res_parent.text}")
                    unprocessed_log.append([product_id, product_name, "Parent assign failed"])

                # Assign to variants
                for i, variant in enumerate(variants, start=1):
                    if i < len(existing_images):
                        doc_id = existing_images[i]["document_id"]
                    else:
                        doc_id = parent_doc_id
                        print(f"⚠️ Not enough images. Using parent image for variant {variant.get('sku')}.")

                    variant_id = variant.get("variant_id") or variant.get("id") or variant.get("item_id")
                    sku = variant.get("sku")
                    payload = {"document_ids": [doc_id]}
                    res_v = requests.put(f"{BASE_URL}/variants/{variant_id}?organization_id={ORG_ID}",
                                         json=payload,
                                         headers={"Authorization": f"Zoho-oauthtoken {access_token}",
                                                  "X-com-zoho-commerce-organizationid": ORG_ID,
                                                  "Content-Type": "application/json"})
                    if res_v.status_code in (200, 201):
                        print(f"✅ {variant.get('name')} (SKU {sku}) ← Image {doc_id}")
                        processed_log.append([product_id, product_name, variant_id, sku, doc_id])
                    else:
                        print(f"❌ Failed for {sku}: {res_v.status_code} {res_v.text}")
                        unprocessed_log.append([product_id, product_name, f"Variant {sku} assign failed"])

        # Export logs at the end of Mode 2
        export_logs_to_excel(processed_log, unprocessed_log)

    else:
        print("❌ Invalid mode selected. Exiting.")


if __name__ == "__main__":
    while True:
        main()
        again = input("\n🔄 Do you want to perform another action? (y/n): ").strip().lower()
        if again != "y":
            print("👋 Exiting. Goodbye!")
            break