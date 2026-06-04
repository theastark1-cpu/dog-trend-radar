#!/usr/bin/env python3
"""Scrape Kickstarter for dog/pet-related projects.

Usage: python3 scrapers/kickstarter_scraper.py
Output: data/kickstarter_signals.json
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

SEARCH_TERMS = ["dogs", "dog", "puppy", "pet"]
BASE_URL = "https://www.kickstarter.com/projects/search.json"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "kickstarter_signals.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
}
REQUEST_DELAY = 2.0


def scrape_term(session, term):
    """Search Kickstarter for a given term."""
    print(f"  Searching for '{term}'...")
    params = {
        "term": term,
        "sort": "popularity",
        "page": 1,
    }

    try:
        resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

    projects = []
    for proj in data.get("projects", [])[:25]:
        projects.append({
            "name": proj.get("name", ""),
            "blurb": proj.get("blurb", ""),
            "pledged": proj.get("pledged", 0),
            "goal": proj.get("goal", 0),
            "backers_count": proj.get("backers_count", 0),
            "state": proj.get("state", ""),
            "country": proj.get("country", ""),
            "currency": proj.get("currency", ""),
            "created_at": proj.get("created_at", 0),
            "deadline": proj.get("deadline", 0),
            "urls": proj.get("urls", {}).get("web", {}).get("project", ""),
            "category": proj.get("category", {}).get("name", ""),
        })

    print(f"  Found {len(projects)} projects")
    return projects


def deduplicate(projects):
    """Remove duplicate projects by URL."""
    seen = set()
    unique = []
    for p in projects:
        url = p.get("urls", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(p)
    return unique


def main():
    print("🐕 Kickstarter Scraper - Dog/Pet Projects")
    print(f"  Search terms: {SEARCH_TERMS}")

    session = requests.Session()
    session.headers.update(HEADERS)

    all_projects = []
    for term in SEARCH_TERMS:
        projects = scrape_term(session, term)
        all_projects.extend(projects)
        time.sleep(REQUEST_DELAY)

    unique = deduplicate(all_projects)

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "projects": unique,
        "total_unique": len(unique),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(unique)} unique projects to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()