#!/usr/bin/env python3
"""Scrape Amazon Pet Supplies Movers & Shakers page.

Usage: python3 scrapers/amazon_scraper.py
Output: data/amazon_signals.json
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.amazon.com/gp/movers-and-shakers/pet-supplies/"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "amazon_signals.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


def parse_rank_change(text):
    """Parse rank change from text like '▲ 1,234 (1,234%)' or '▼ 50'."""
    if not text:
        return {"direction": "unknown", "value": 0, "percentage": 0}

    text = text.strip()
    direction = "unknown"
    if "▲" in text or "up" in text.lower():
        direction = "up"
    elif "▼" in text or "down" in text.lower():
        direction = "down"

    # Extract numbers
    import re
    numbers = re.findall(r'[\d,]+', text)
    value = int(numbers[0].replace(",", "")) if numbers else 0
    percentage = int(numbers[1].replace(",", "")) if len(numbers) > 1 else 0

    return {"direction": direction, "value": value, "percentage": percentage}


def scrape():
    """Scrape Amazon Movers & Shakers page."""
    print("🐕 Amazon Movers & Shakers Scraper")
    print(f"  URL: {URL}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        resp = session.get(URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching page: {e}")
        return {"scraped_at": datetime.now(timezone.utc).isoformat(), "products": [], "error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")
    products = []

    # Amazon Movers & Shakers uses various selectors. Try multiple approaches
    # Main product cards
    product_cards = soup.select(".a-section.a-spacing-none.p13n-asin, .zg-item, #zg-ordered-list .zg-item-immersion")
    if not product_cards:
        # Fallback: try alternative selectors
        product_cards = soup.select("[data-asin]")

    print(f"  Found {len(product_cards)} product cards")

    for card in product_cards[:50]:
        try:
            # Title
            title_el = (
                card.select_one(".p13n-sc-truncate-desktop-type2, .p13n-sc-truncated, .a-link-normal .a-text-normal") or
                card.select_one("[title]") or
                card.select_one("img[alt]")
            )
            title = ""
            if title_el:
                title = title_el.get("title", "") or title_el.get("alt", "") or title_el.get_text(strip=True)

            # Rank change
            rank_change_el = card.select_one(".zg-percent-change, .p13n-sc-ranking-change, .a-size-small.a-color-success, .a-size-small.a-color-danger")
            rank_change_text = rank_change_el.get_text(strip=True) if rank_change_el else ""
            rank_change = parse_rank_change(rank_change_text)

            # Price
            price_el = card.select_one(".p13n-sc-price, .a-price .a-offscreen, .a-color-price")
            price = price_el.get_text(strip=True) if price_el else ""

            # Rating
            rating_el = card.select_one(".a-icon-alt, .a-icon-star-small")
            rating = rating_el.get_text(strip=True).split()[0] if rating_el else ""

            # Review count
            review_el = card.select_one(".a-size-small.a-color-secondary, .a-size-base")
            review_count = review_el.get_text(strip=True) if review_el else ""

            # Link
            link_el = card.select_one("a.a-link-normal")
            link = ""
            if link_el:
                href = link_el.get("href", "")
                if href and isinstance(href, str) and str(href).startswith("/"):
                    link = "https://www.amazon.com" + str(href)
                else:
                    link = str(href) if href else ""

            products.append({
                "title": title,
                "rank_change": rank_change,
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "url": link,
            })
        except Exception as e:
            print(f"  WARNING: Error parsing product card: {e}")
            continue

    print(f"  Parsed {len(products)} products")

    return {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "products": products,
    }


def main():
    result = scrape()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(result['products'])} products to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()