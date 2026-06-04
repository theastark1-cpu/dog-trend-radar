#!/usr/bin/env python3
"""Scrape upcoming vet conference agendas for emerging clinical topics and product trends.

Sources: VMX (Navc.com), WVC (wvc.org), AVMA (avma.org)

Usage: python3 scrapers/vet_conference_scraper.py
Output: data/vet_conference_signals.json
"""

import json
import time
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Conference sources to scrape
CONFERENCE_SOURCES = [
    {
        "name": "VMX (Veterinary Meeting & Expo)",
        "url": "https://navc.com/vmx/schedule/",
        "selector": ".session-title, .session, .agenda-item, .schedule-item",
    },
    {
        "name": "WVC Annual Conference",
        "url": "https://wvc.org/education/schedule/",
        "selector": ".session-title, .session, .agenda-item, .event-title",
    },
    {
        "name": "AVMA Convention",
        "url": "https://www.avma.org/events/avma-convention",
        "selector": ".session-title, .session, .agenda-item, .event-title, .schedule-session",
    },
]

# Also try to scrape conference listing pages
CONFERENCE_LISTINGS = [
    {
        "name": "Vet Shows Calendar",
        "url": "https://www.vetshows.com/",
        "selector": ".event, .conference, .show-item",
    },
]

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "vet_conference_signals.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_DELAY = 2.0

# Emerging clinical topics to look for
TREND_KEYWORDS = [
    "telemedicine", "telehealth", "AI", "artificial intelligence", "machine learning",
    "CBD", "cannabidiol", "probiotics", "microbiome", "gut health",
    "immunotherapy", "monoclonal antibody", "gene therapy", "stem cell",
    "digital health", "wearable", "remote monitoring", "biosensor",
    "nutrition", "fresh food", "raw diet", "alternative protein",
    "behavioral", "anxiety", "CBD oil", "calming",
    "minimally invasive", "laparoscopic", "regenerative medicine",
    "one health", "zoonotic", "antimicrobial resistance",
    "point of care", "diagnostics", "rapid test", "biomarker",
    "pain management", "laser therapy", "acupuncture", "physical therapy",
    "dentistry", "oral health", "periodontal",
    "dermatology", "allergy", "atopic dermatitis", "cytopoint",
    "oncology", "chemotherapy", "targeted therapy",
    "cardiology", "heart disease", "MMVD",
    "orthopedic", "TPLO", "joint", "arthritis", "OA",
    "rehabilitation", "hydrotherapy", "canine fitness",
]


def scrape_conference_source(session, conf):
    """Scrape a conference agenda page."""
    name = conf["name"]
    url = conf["url"]
    print(f"  Scraping {name}: {url}")

    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"    ERROR: {e}")
        return {"conference": name, "url": url, "sessions": [], "topics": [], "error": str(e)}

    soup = BeautifulSoup(resp.text, "lxml")

    # Extract all text content
    text = soup.get_text(separator=" ", strip=True)

    # Try to find session titles with multiple selectors
    sessions = []
    selectors_to_try = [
        ".session-title", ".session h3", ".session h4", ".agenda-item h3",
        ".schedule-item h3", ".event-title", "h3", "h2",
        "[class*='session']", "[class*='Session']",
    ]

    for selector in selectors_to_try:
        elements = soup.select(selector)
        if elements:
            for el in elements[:30]:
                title = el.get_text(strip=True)
                if title and len(title) > 10:
                    sessions.append(title)
            if sessions:
                break

    # If no structured sessions found, extract paragraphs that look like session descriptions
    if not sessions:
        paragraphs = soup.select("p, li, .content li, .description")
        for p in paragraphs[:50]:
            text_p = p.get_text(strip=True)
            if len(text_p) > 20 and len(text_p) < 300:
                sessions.append(text_p)

    # Extract topic keywords
    topics = extract_topics(sessions, text)

    return {
        "conference": name,
        "url": url,
        "sessions": sessions[:20],  # Cap at 20
        "topics": topics,
        "session_count_found": len(sessions),
    }


def extract_topics(sessions, page_text):
    """Extract emerging topic keywords from sessions and page text."""
    all_text = " ".join(sessions) + " " + page_text
    all_text_lower = all_text.lower()

    topics = []
    for keyword in TREND_KEYWORDS:
        count = all_text_lower.count(keyword.lower())
        if count > 0:
            topics.append({"keyword": keyword, "mentions": count})

    topics.sort(key=lambda x: x["mentions"], reverse=True)
    return topics


def get_conference_schedule():
    """Return known upcoming vet conferences as structured data."""
    return [
        {
            "name": "VMX 2026",
            "organizer": "NAVC",
            "dates": "January 17-21, 2026",
            "location": "Orlando, FL",
            "url": "https://navc.com/vmx/",
            "focus_areas": ["Small animal", "Exotics", "Practice management", "Technician", "Wellness"],
        },
        {
            "name": "WVC 97th Annual Conference",
            "organizer": "WVC",
            "dates": "March 1-4, 2026",
            "location": "Las Vegas, NV",
            "url": "https://wvc.org/",
            "focus_areas": ["Clinical CE", "Hands-on labs", "Practice management", "Technician tracks"],
        },
        {
            "name": "AVMA Convention 2026",
            "organizer": "AVMA",
            "dates": "July 9-14, 2026",
            "location": "San Diego, CA",
            "url": "https://www.avma.org/events/avma-convention",
            "focus_areas": ["Continuing education", "Exhibit hall", "Networking", "Wellness"],
        },
        {
            "name": "ACVIM Forum 2026",
            "organizer": "ACVIM",
            "dates": "June 10-13, 2026",
            "location": "Montreal, Canada",
            "url": "https://www.acvim.org/",
            "focus_areas": ["Internal medicine", "Cardiology", "Neurology", "Oncology", "Nutrition"],
        },
        {
            "name": "Fetch dvm360 Conference",
            "organizer": "dvm360",
            "dates": "August 2026",
            "location": "Kansas City, MO",
            "url": "https://www.fetchdvm360.com/",
            "focus_areas": ["Clinical", "Practice management", "Technician", "Wellness"],
        },
        {
            "name": "AAHA Con 2026",
            "organizer": "AAHA",
            "dates": "September 2026",
            "location": "National Harbor, MD",
            "url": "https://www.aaha.org/",
            "focus_areas": ["AAHA standards", "Practice accreditation", "Team training", "Clinical updates"],
        },
    ]


def main():
    print("🐕 Veterinary Conference Scraper")
    print(f"  Sources: {len(CONFERENCE_SOURCES)} conference sites")

    session = requests.Session()
    session.headers.update(HEADERS)

    conference_data = []

    # Scrape conference agenda pages
    for conf in CONFERENCE_SOURCES:
        data = scrape_conference_source(session, conf)
        conference_data.append(data)
        time.sleep(REQUEST_DELAY)

    # Aggregate all topics across conferences
    all_topics = Counter()
    for conf_data in conference_data:
        for topic in conf_data.get("topics", []):
            all_topics[topic["keyword"]] += topic["mentions"]

    emerging_topics = [
        {"keyword": k, "total_mentions": v}
        for k, v in all_topics.most_common(30)
    ]

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "conferences": conference_data,
        "known_upcoming_conferences": get_conference_schedule(),
        "aggregated_emerging_topics": emerging_topics,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(conference_data)} conferences + {len(get_conference_schedule())} upcoming to {OUTPUT_FILE}")
    if emerging_topics:
        print(f"  Top emerging topics: {', '.join(t['keyword'] for t in emerging_topics[:5])}")


if __name__ == "__main__":
    main()
