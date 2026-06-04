#!/usr/bin/env python3
"""Scrape Chewy "New Arrivals" and Petco "New Products" pages for dog product trends.

Usage: python3 scrapers/retail_scraper.py
Output: data/retail_signals.json
"""

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

RETAIL_SOURCES = [
    {
        "name": "Chewy New Arrivals",
        "url": "https://www.chewy.com/b/new-arrivals-3368",
        "category": "General Pet",
    },
    {
        "name": "Chewy Dog New Arrivals",
        "url": "https://www.chewy.com/b/dog-288?sort=NEW_ARRIVALS",
        "category": "Dog",
    },
    {
        "name": "Petco New Arrivals",
        "url": "https://www.petco.com/shop/en/petcostore/category/new-arrivals",
        "category": "General Pet",
    },
    {
        "name": "Petco Dog New Arrivals",
        "url": "https://www.petco.com/shop/en/petcostore/category/dog-new-arrivals",
        "category": "Dog",
    },
]

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "retail_signals.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}
REQUEST_DELAY = 2.0


def scrape_chewy(session, source):
    """Scrape Chewy product listings."""
    url = source["url"]
    name = source["name"]
    print(f"  Scraping {name}: {url}")

    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"    ERROR: {e}")
        return {"source": name, "url": url, "products": [], "error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")
    products = []

    # Chewy product card selectors
    selectors = [
        ".product-card", ".product", "[data-product-id]",
        ".kib-product-card", "article", "[class*='product']",
        ".product-holder", ".slick-slide",
    ]

    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    if not cards:
        # Fallback: look for product-like elements
        # Look for images with product names
        img_links = soup.select("a[href*='/dp/'], a[href*='/product/'], a[href*='/shop/']")
        for link in img_links[:50]:
            try:
                title = ""
                img = link.select_one("img")
                if img:
                    title = img.get("alt", "")
                if not title:
                    title = link.get("aria-label", "")
                if not title:
                    title = link.get_text(strip=True)

                # Price
                price_el = link.parent.select_one(".price, .product-price, [class*='price'], .sale-price")
                price = price_el.get_text(strip=True) if price_el else ""

                if title and len(title) > 5:
                    products.append({
                        "title": title,
                        "price": price,
                        "url": url,
                    })
            except Exception:
                continue
    else:
        for card in cards[:50]:
            try:
                # Title
                title_el = (
                    card.select_one(".product-title, .product-name, h3, h4, .name, [data-name]")
                    or card.select_one("img[alt]")
                )
                title = ""
                if title_el:
                    title = title_el.get("alt", "") or title_el.get("title", "") or title_el.get_text(strip=True)

                # Price
                price_el = card.select_one(".price, .product-price, .our-price, [class*='price'], .sale-price")
                price = price_el.get_text(strip=True) if price_el else ""

                # Category
                cat_el = card.select_one(".product-category, .category, .brand")
                category = cat_el.get_text(strip=True) if cat_el else source.get("category", "")

                if title and len(title) > 5:
                    products.append({
                        "title": title,
                        "price": price,
                        "category": category,
                        "url": url,
                    })
            except Exception as e:
                continue

    print(f"    Found {len(products)} products")

    # Extract category trends from product titles
    categories = Counter()
    keywords = Counter()
    for p in products:
        title_lower = p.get("title", "").lower()
        # Categorize
        if any(w in title_lower for w in ["food", "treat", "chew", "kibble", "dental"]):
            categories["Food & Treats"] += 1
        if any(w in title_lower for w in ["toy", "ball", "rope", "squeak", "puzzle", "chew toy"]):
            categories["Toys"] += 1
        if any(w in title_lower for w in ["collar", "leash", "harness", "bandana", "clothes", "jacket", "sweater"]):
            categories["Apparel & Accessories"] += 1
        if any(w in title_lower for w in ["bed", "crate", "kennel", "blanket", "mat"]):
            categories["Beds & Crates"] += 1
        if any(w in title_lower for w in ["groom", "shampoo", "brush", "nail", "clipper"]):
            categories["Grooming"] += 1
        if any(w in title_lower for w in ["health", "supplement", "vitamin", "probiotic", "cbd", "oil"]):
            categories["Health & Wellness"] += 1
        if any(w in title_lower for w in ["bowl", "feeder", "fountain", "mat", "slow feed"]):
            categories["Bowls & Feeders"] += 1
        if any(w in title_lower for w in ["training", "clicker", "pad", "gate", "pen"]):
            categories["Training"] += 1
        if any(w in title_lower for w in ["tech", "gps", "tracker", "camera", "smart", "automatic"]):
            categories["Tech & Gadgets"] += 1

    return {
        "source": name,
        "url": url,
        "products": products[:50],
        "category_breakdown": dict(categories.most_common()),
    }


def main():
    print("🐕 Retail Scraper - Chewy & Petco New Arrivals")
    print(f"  Sources: {len(RETAIL_SOURCES)}")

    session = requests.Session()
    session.headers.update(HEADERS)

    all_sources = []

    for source in RETAIL_SOURCES:
        data = scrape_chewy(session, source)
        all_sources.append(data)
        time.sleep(REQUEST_DELAY)

    # Aggregate category trends
    total_products = sum(len(s.get("products", [])) for s in all_sources)
    aggregate_categories = Counter()
    for s in all_sources:
        for cat, count in s.get("category_breakdown", {}).items():
            aggregate_categories[cat] += count

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "sources": all_sources,
        "total_products_found": total_products,
        "aggregate_category_trends": dict(aggregate_categories.most_common()),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {total_products} products from {len(all_sources)} sources to {OUTPUT_FILE}")
    if aggregate_categories:
        print(f"  Top categories: {', '.join(f'{k}({v})' for k, v in aggregate_categories.most_common(5))}")


if __name__ == "__main__":
    main()
