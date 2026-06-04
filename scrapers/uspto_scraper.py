#!/usr/bin/env python3
"""Scrape USPTO patent database for dog/pet-related recent patents.

Usage: python3 scrapers/uspto_scraper.py
Output: data/uspto_signals.json
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# USPTO Patent Public Search API (Bulk Data API)
# Try multiple endpoints
SEARCH_QUERIES = [
    "dog+pet",
    "canine",
    "dog+toy",
    "dog+food",
    "dog+health",
]

# USPTO Open Data API
API_URL = "https://developer.uspto.gov/ibd-api/v1/application/grants"
# Fallback: USPTO PatentsView API
PATENTSVIEW_URL = "https://api.patentsview.org/patents/query"

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "uspto_signals.json"
HEADERS = {
    "User-Agent": "DogTrendRadar/1.0 (research@example.com)",
    "Accept": "application/json",
}
REQUEST_DELAY = 2.0


def search_uspto_api(session, query, rows=25):
    """Search USPTO IB API."""
    params = {
        "searchText": query,
        "rows": rows,
        "sort": "patentNumber+desc",
        "start": 0,
    }
    try:
        resp = session.get(API_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        return results
    except Exception as e:
        print(f"    USPTO IB API error: {e}")
        return []


def search_patentsview(session, query, rows=25):
    """Search PatentsView API as fallback."""
    # Build query for titles containing dog-related terms
    q = {
        "_and": [
            {"_text_any": {"patent_title": query.replace("+", " ")}},
        ]
    }
    params = {
        "q": json.dumps(q),
        "f": json.dumps([
            "patent_number", "patent_title", "patent_date",
            "patent_abstract", "inventor_first_name", "inventor_last_name",
            "assignee_organization"
        ]),
        "s": json.dumps([{"patent_date": "desc"}]),
        "o": json.dumps({"page": 1, "per_page": rows}),
    }
    try:
        resp = session.get(PATENTSVIEW_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        patents = data.get("patents", [])
        results = []
        for p in patents:
            inventors = []
            for inv in p.get("inventors", []):
                name = f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip()
                if name:
                    inventors.append(name)
            assignees = [a.get("assignee_organization", "") for a in p.get("assignees", [])]
            results.append({
                "patentNumber": p.get("patent_number", ""),
                "title": p.get("patent_title", ""),
                "inventors": "; ".join(inventors),
                "assignee": "; ".join(assignees),
                "filingDate": p.get("patent_date", ""),
                "abstract": p.get("patent_abstract", ""),
            })
        return results
    except Exception as e:
        print(f"    PatentsView API error: {e}")
        return []


def deduplicate(patents):
    """Deduplicate by patent number."""
    seen = set()
    unique = []
    for p in patents:
        num = p.get("patentNumber", "")
        if num and num not in seen:
            seen.add(num)
            unique.append(p)
    return unique


def main():
    print("🐕 USPTO Patent Scraper - Dog/Pet Patents")

    session = requests.Session()
    all_results = []

    # Try PatentsView API first (more reliable, no auth needed)
    print("  Using PatentsView API...")
    for query in SEARCH_QUERIES:
        print(f"  Searching: {query}")
        results = search_patentsview(session, query)
        print(f"    Found {len(results)} patents")
        all_results.extend(results)
        if len(all_results) >= 100:
            break
        time.sleep(REQUEST_DELAY)

    # If few results, also try USPTO IB API
    if len(all_results) < 25:
        print("  Trying USPTO IB API as secondary source...")
        for query in SEARCH_QUERIES[:2]:
            results = search_uspto_api(session, query)
            for r in results:
                r["patentNumber"] = r.get("patentNumber", "")
                r["title"] = r.get("inventionTitle", r.get("title", ""))
            print(f"    Found {len(results)} patents")
            all_results.extend(results)
            time.sleep(REQUEST_DELAY)

    unique = deduplicate(all_results)

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "patents": unique,
        "total_unique": len(unique),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(unique)} unique patents to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
