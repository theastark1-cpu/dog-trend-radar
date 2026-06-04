#!/usr/bin/env python3
"""Quick bootstrap: scrape just the new dog_ailments category."""
import sys, time, random, json, numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from pytrends.request import TrendReq

DATA_DIR = Path(__file__).parent / "data"

KEYWORDS = {
    "dog_ailments": [
        "dog ear infection", "dog skin allergies", "dog diarrhea", "dog vomiting",
        "dog hip dysplasia", "dog arthritis", "dog pancreatitis", "dog UTI",
        "dog cancer", "dog seizures", "dog thyroid problems", "dog kennel cough",
        "dog hot spots", "dog eye infection", "dog heartworm", "dog limping",
        "dog bloating", "dog licking paws",
    ]
}

pt = TrendReq(hl="en-US", tz=420, timeout=20, retries=1, backoff_factor=1)
print("Connected to Google Trends")

all_trends = {}
for cat, keywords in KEYWORDS.items():
    print(f"\n{cat}: {len(keywords)} keywords")
    frames = []
    for kw in keywords:
        try:
            pt.build_payload([kw], cat=0, timeframe="today 3-m", geo="US")
            df = pt.interest_over_time()
            if df is not None and not df.empty and kw in df.columns:
                frames.append(df[[kw]])
                print(f"  ✓ {kw:<30s} {len(df)} days (latest: {int(df[kw].iloc[-1]) if len(df)>0 else '?'})")
            else:
                print(f"  ⚠ {kw:<30s} no data")
        except Exception as e:
            print(f"  ✗ {kw:<30s} {e}")
        time.sleep(45 + random.uniform(1, 5))

    if frames:
        combined = pd.concat(frames, axis=1)
        path = DATA_DIR / f"iot_{cat}.csv"
        combined.to_csv(path)
        print(f"  ✓ Saved {combined.shape[0]} rows × {combined.shape[1]} keywords to {path}")
        all_trends[cat] = combined

# Merge into all_trends.csv
existing = pd.read_csv(DATA_DIR / "all_trends.csv")
for cat, df in all_trends.items():
    if df is not None and not df.empty:
        melted = df.reset_index().melt(id_vars=["date"], var_name="keyword", value_name="interest")
        melted["category"] = cat
        existing = pd.concat([existing, melted], ignore_index=True)

existing.to_csv(DATA_DIR / "all_trends.csv", index=False)
print(f"\n✅ all_trends.csv: {len(existing)} rows with {existing['keyword'].nunique()} keywords")

# Regenerate summary
from trend_scraper import generate_summary as gen_summary
summary = gen_summary(all_trends)

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.ndarray,)): return obj.tolist()
        return super().default(obj)

with open(DATA_DIR / "summary.json", "w") as f:
    json.dump(summary, f, indent=2, cls=NpEncoder)

print(f"✅ summary.json: {len(summary['trend_movers'])} movers, {len(summary['keyword_snapshot'])} keywords")
print(f"   New ailment keywords: {sum(1 for k in summary['keyword_snapshot'] if k.startswith('dog_ailments'))}")
