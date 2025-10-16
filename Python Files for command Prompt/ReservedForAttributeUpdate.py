def fetch_products(token, filter_skus=None, max_workers=2, max_retries=3, delay_between_requests=0.2):
    """
    Fetch Zoho Commerce products with attributes, choices, and variant counts.
    - filter_skus: List of SKUs to filter. If None, fetch all products.
    """
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    products_data = []
    filter_skus = set(filter_skus) if filter_skus else None

    def fetch_product_detail(product_id):
        url = f"{API_BASE_URL}/products/{product_id}"
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(url, headers=headers, params={"organization_id": ORG_ID}, timeout=10)
                if resp.status_code == 200:
                    details = resp.json().get("product", {})
                    variants = details.get("variants", [])

                    # --- Build attribute → choice → count map ---
                    attr_map = {}
                    for attr in details.get("attributes", []):
                        attr_name = attr.get("name")
                        attr_map[attr_name] = {}
                        for choice in attr.get("choices", []):
                            choice_val = choice.get("value")
                            # Count how many variants use this choice
                            count = sum(
                                1 for v in variants
                                for av in v.get("attributes", [])
                                if av.get("name") == attr_name and av.get("value") == choice_val
                            )
                            attr_map[attr_name][choice_val] = count

                    product_info = {
                        "id": details.get("id") or details.get("product_id"),
                        "name": details.get("name") or "Unnamed Product",
                        "sku": details.get("sku") or (variants[0]["sku"] if variants else "N/A"),
                        "variants_count": len(variants),
                        "variants": [
                            {
                                "name": v.get("name"),
                                "sku": v.get("sku"),
                                "attributes": v.get("attributes", [])
                            } for v in variants
                        ],
                        "attributes": [
                            {
                                "name": attr_name,
                                "choices": [
                                    {"value": val, "variant_count": count}
                                    for val, count in choices.items()
                                ]
                            } for attr_name, choices in attr_map.items()
                        ]
                    }

                    # Filter by SKU
                    if filter_skus and product_info["sku"] not in filter_skus:
                        return None
                    return product_info

                elif resp.status_code == 429:
                    wait = 2 ** attempt
                    print(f"⏳ Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"⚠️ Error fetching product {product_id}: {resp.status_code} {resp.text}")
                    return None
            except requests.exceptions.Timeout:
                print(f"⏳ Timeout fetching product {product_id}, retry {attempt}/{max_retries}")
            except Exception as e:
                print(f"❌ Error fetching product {product_id}: {e}")
            time.sleep(delay_between_requests)
        return None

    def get_product_id(p):
        return p.get("product_id") or p.get("id")

    page = 1
    while True:
        try:
            resp = requests.get(
                f"{API_BASE_URL}/products",
                headers=headers,
                params={"page": page, "per_page": 200, "organization_id": ORG_ID},
                timeout=10
            )
            if resp.status_code != 200:
                print(f"❌ API error {resp.status_code}: {resp.text}")
                break
            data = resp.json()
            products = data.get("products") or data.get("data", {}).get("products")
            if not products:
                print(f"✅ No more products found on page {page}. Done.")
                break
        except Exception as e:
            print(f"❌ Error fetching product list page {page}: {e}")
            break

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {}
            for p in products:
                pid = get_product_id(p)
                if pid:
                    future_to_id[executor.submit(fetch_product_detail, pid)] = pid

            for future in as_completed(future_to_id):
                try:
                    product_info = future.result(timeout=15)
                    if product_info:
                        products_data.append(product_info)
                        print(f"✅ {product_info['name']} (SKU: {product_info['sku']}) "
                              f"Variants: {product_info['variants_count']} | "
                              f"Attributes: {[a['name'] for a in product_info['attributes']]}")
                    time.sleep(delay_between_requests)
                except Exception as e:
                    print(f"⚠️ Task failed: {e}")

        page += 1

    return products_data
