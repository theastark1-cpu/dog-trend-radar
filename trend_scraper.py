#!/usr/bin/env python3
"""
Dog Trend Radar — Google Trends scraper focused exclusively on the dog economy.
Tracks products, services, health, owner searches, tech, and investments.
Uses single-keyword requests with generous delays to avoid rate limiting.
"""

import json
import time
import random
import numpy as np
from datetime import datetime
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Keywords organized by sub-category ──
# Each category maps to a color in the dashboard
KEYWORDS = {
    "dog_products": [
        # Product categories + direct purchase intent
        "pet insurance",           # Anchor: $4.3B US market, recurring revenue
        "dog food delivery",       # DTC subscription — Farmers Dog, Ollie, Nom Nom
        "fresh dog food",          # Human-grade trend (+13.4% YoY growth)
        "smart dog collar",        # Pet wearables — Fi, Whistle, Tractive ($15.9B → $36.3B by 2033)
        "dog DNA test",            # Embark, Wisdom Panel — $448M market expanding into vet-channel
        "dog subscription box",    # BarkBox, Bullymake — $300M+ DTC subscription market
        "dog supplements",         # Joint, skin, calming, probiotic — fastest-growing pet category
        "CBD for dogs",            # Massive interest spike 2025, regulatory tailwinds
        "GPS dog tracker",         # Tractive, Fi, AirTag collars — escape prevention
        "dog toys",                # Broad category anchor — Kong, Chewy private label
    ],
    "dog_services": [
        # Service businesses — recurring revenue models
        "dog grooming",            # $10B+ US grooming market, mobile is the high-margin play
        "dog daycare",             # $4.5B US market, 5.7% CAGR
        "dog boarding",            # Rover, Wag — $4B gig economy pet segment
        "dog training",            # In-person + virtual — behavioral training demand surging
        "dog walker",              # Gig economy — Wag, Rover, local
        "mobile dog grooming",     # Higher-margin variant, franchise model emerging
        "dog photography",         # Niche creative service, wedding + family sessions
    ],
    "dog_health": [
        # What owners actually search — health, breeds, behavior
        "best dog food",           # Top-of-funnel: highest-volume nutrition query
        "dog allergies",           # Itching, food trials, Apoquel searches
        "puppy training",          # Housebreaking, crate, bite inhibition
        "dog separation anxiety",  # Post-COVID return-to-office driver
        "hypoallergenic dogs",     # Doodle demand — Goldendoodle, Labradoodle
        "dog probiotic",           # Gut health trend crossing from human to pet
        "dog skin problems",       # Dermatology — #1 vet visit reason
        "dog anxiety",             # Calming chews, vests, CBD, medication
    ],
    "dog_tech_investment": [
        # Tech, startups, investment signals
        "pet tech",                # Startup ecosystem signal
        "veterinary telehealth",   # 20% CAGR to $1.9B — post-COVID normalization watch
        "dog health app",          # Pet wellness trackers, symptom checkers
        "pet wellness",            # Holistic health trend, preventive care
        "dog breeding business",   # Entrepreneur signal — doodle breeders, home-based
        "dog franchise",           # Camp Bow Wow, Dogtopia, Pet Supplies Plus
    ],
}

GEO = "US"
DELAY = 45  # Seconds between keyword requests


def get_pt():
    for attempt in range(3):
        try:
            return TrendReq(hl="en-US", tz=420, timeout=20, retries=1, backoff_factor=1)
        except Exception as e:
            print(f"  Connect retry {attempt+1}: {e}")
            time.sleep(15)
    raise RuntimeError("Cannot connect to Google Trends")


def sleep():
    time.sleep(DELAY + random.uniform(1, 5))


def scrape_iot(pt, category, keywords):
    """Scrape interest_over_time one keyword at a time."""
    print(f"\n{'─'*40}")
    print(f"  {category.upper()}")
    print(f"{'─'*40}")
    frames = []

    for kw in keywords:
        try:
            pt.build_payload([kw], cat=0, timeframe="today 3-m", geo=GEO)
            df = pt.interest_over_time()
            if df is not None and not df.empty and kw in df.columns:
                frames.append(df[[kw]])
                latest_val = int(df[kw].iloc[-1]) if len(df) > 0 else "?"
                print(f"  ✓ {kw:<35s} {len(df)} days  (latest: {latest_val})")
            else:
                print(f"  ⚠ {kw:<35s} no data")
        except Exception as e:
            print(f"  ✗ {kw:<35s} {e}")

        sleep()

    if frames:
        combined = pd.concat(frames, axis=1)
        # Load existing and merge
        path = DATA_DIR / f"iot_{category}.csv"
        if path.exists():
            existing = pd.read_csv(path, index_col=0, parse_dates=True)
            combined = combined.combine_first(existing)
        combined = combined.sort_index()
        combined.to_csv(path)
        print(f"  ✓ Saved {combined.shape[0]} rows × {combined.shape[1]} keywords")
        return combined
    return None


def generate_summary(all_trends):
    """Generate summary: trend movers, top keywords."""
    summary = {
        "scraped_at": datetime.now().isoformat(),
        "trend_movers": [],
        "keyword_snapshot": {},
    }

    today = pd.Timestamp.now(tz="UTC")
    cutoff_recent = today - pd.Timedelta(days=30)
    cutoff_prior_start = today - pd.Timedelta(days=60)
    cutoff_week = today - pd.Timedelta(days=7)

    for cat, df in all_trends.items():
        if df is None or df.empty:
            continue
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        # Localize if tz-naive
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")

        recent = df[df.index >= cutoff_recent]
        prior = df[(df.index >= cutoff_prior_start) & (df.index < cutoff_recent)]
        week = df[df.index >= cutoff_week]

        for col in df.columns:
            try:
                r_avg = recent[col].mean()
                p_avg = prior[col].mean()
                w_avg = week[col].mean()
                latest = df[col].iloc[-1]

                if pd.isna(r_avg) or pd.isna(p_avg) or p_avg <= 1:
                    continue

                chg = ((r_avg - p_avg) / p_avg) * 100
                if abs(chg) > 8:
                    summary["trend_movers"].append({
                        "keyword": col,
                        "category": cat,
                        "change_pct": round(chg, 1),
                        "recent_avg": round(r_avg, 1),
                        "prior_avg": round(p_avg, 1),
                        "latest": round(latest, 1),
                    })

                summary["keyword_snapshot"][f"{cat}/{col}"] = {
                    "latest": round(latest, 1),
                    "week_avg": round(w_avg, 1) if pd.notna(w_avg) else None,
                    "month_avg": round(r_avg, 1),
                }
            except Exception:
                pass

    summary["trend_movers"].sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return summary


def main():
    print(f"\n{'='*60}")
    print(f"  🐕 DOG TREND RADAR — {datetime.now().isoformat()}")
    print(f"{'='*60}")
    pt = get_pt()

    all_trends = {}
    for cat, keywords in KEYWORDS.items():
        df = scrape_iot(pt, cat, keywords)
        all_trends[cat] = df

    # ── Combine & save unified CSV ──
    combined_parts = []
    for cat, df in all_trends.items():
        if df is not None and not df.empty:
            melted = df.reset_index().melt(
                id_vars=["date"], var_name="keyword", value_name="interest"
            )
            melted["category"] = cat
            combined_parts.append(melted)

    if combined_parts:
        combined = pd.concat(combined_parts, ignore_index=True)
        combined.to_csv(DATA_DIR / "all_trends.csv", index=False)
        print(f"\n✓ Combined CSV: {len(combined)} rows")

    summary = generate_summary(all_trends)

    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, (np.ndarray,)): return obj.tolist()
            return super().default(obj)

    with open(DATA_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, cls=NpEncoder)

    # ── Print summary ──
    print(f"\n{'='*60}")
    print("  📊 SIGNALS")
    print(f"{'='*60}")

    if summary["trend_movers"]:
        print("\n📈 30-DAY TREND MOVERS:")
        for item in summary["trend_movers"]:
            d = "▲" if item["change_pct"] > 0 else "▼"
            print(f"  {d} {item['change_pct']:+.1f}% | {item['keyword']} ({item['category']}) | "
                  f"latest: {item['latest']} | recent avg: {item['recent_avg']}")

    print(f"\n📊 KEYWORD SNAPSHOT:")
    for key, snap in summary["keyword_snapshot"].items():
        print(f"  {key}: latest={snap['latest']}, week_avg={snap['week_avg']}")

    print(f"\n✓ Done — {len(KEYWORDS)} categories, {sum(len(v) for v in KEYWORDS.values())} keywords")


if __name__ == "__main__":
    main()
