#!/usr/bin/env python3
"""
Lead-Lag Correlation Engine
For every pair of keywords across all categories, compute cross-correlation
at various lags (0-90 days). Identify leader-follower relationships where
one keyword's movement predicts another's with correlation > 0.7.

Approach:
1. Compute 7-day rolling average to smooth out weekly noise.
2. Cross-correlate the smoothed series at lags 0-90.
3. Also try first-differenced series to detect change-leadership.
"""

import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import combinations

warnings.filterwarnings("ignore", category=RuntimeWarning)

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT = DATA_DIR / "lead_lag_pairs.json"
ALL_TRENDS = DATA_DIR / "all_trends.csv"
MAX_LAG_DAYS = 90
CORRELATION_THRESHOLD = 0.7
DIFF_THRESHOLD = 0.55  # Lower threshold for differenced series (more noise)
TOP_N = 50


def load_pivot(df_long):
    """Convert long-format all_trends.csv into a keyword × date pivot table."""
    pivot = df_long.pivot_table(
        index="date", columns="keyword", values="interest", aggfunc="mean"
    )
    pivot.index = pd.to_datetime(pivot.index, format='mixed')
    pivot = pivot.sort_index()
    pivot = pivot.ffill().dropna(axis=1, how="all")
    return pivot


def cross_correlate(series_a, series_b, max_lag):
    """
    Compute cross-correlation between two aligned series.
    Returns (best_lag, best_corr, all_lag_corrs).
    Positive lag means series_b[t - lag] correlates with series_a[t]
    i.e., series_b leads series_a.
    """
    a = series_a.values.astype(float)
    b = series_b.values.astype(float)

    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]

    if len(a) < max_lag + 5:
        return 0, 0.0, {}

    best_corr = -1.0
    best_lag = 0
    lag_corrs = {}

    for lag in range(0, min(max_lag + 1, len(a) - 5)):
        if lag == 0:
            aligned_a, aligned_b = a, b
        else:
            aligned_a = a[lag:]
            aligned_b = b[:-lag]

        if len(aligned_a) < 5:
            continue

        corr = np.corrcoef(aligned_a, aligned_b)[0, 1]
        if np.isnan(corr):
            corr = 0.0
        lag_corrs[lag] = float(corr)

        if corr > best_corr:
            best_corr = corr
            best_lag = lag

    return best_lag, best_corr, lag_corrs


def run_lead_lag():
    """Main entry point."""
    print("=" * 60)
    print("  LEAD-LAG CORRELATION ENGINE")
    print("=" * 60)

    df = pd.read_csv(ALL_TRENDS)
    pivot = load_pivot(df)
    keywords = list(pivot.columns)
    print(f"  Loaded {len(keywords)} keywords × {len(pivot)} days")

    # Keyword → category map
    kw_to_cat = {}
    for _, row in df.iterrows():
        kw_to_cat[row["keyword"]] = row["category"]

    # ── Pass 1: Smoothed series (7-day rolling) for medium-term lead-lag ──
    print("\n  Pass 1: 7-day smoothed series — medium-term lead-lag")
    smooth_pivot = pivot.rolling(window=7, min_periods=7).mean().dropna()

    smooth_results = []
    for kw_a, kw_b in combinations(keywords, 2):
        common = smooth_pivot[[kw_a, kw_b]].dropna()
        if len(common) < 21:
            continue

        # b leads a
        lag_ba, corr_ba, all_corrs_ba = cross_correlate(common[kw_b], common[kw_a], min(MAX_LAG_DAYS, len(common) // 2))
        # a leads b
        lag_ab, corr_ab, all_corrs_ab = cross_correlate(common[kw_a], common[kw_b], min(MAX_LAG_DAYS, len(common) // 2))

        if corr_ba >= CORRELATION_THRESHOLD and lag_ba > 0:
            lag0 = all_corrs_ba.get(0, 0)
            smooth_results.append({
                "leader": kw_b,
                "follower": kw_a,
                "lag_days": int(lag_ba),
                "correlation": round(float(corr_ba), 4),
                "lag0_correlation": round(float(lag0), 4),
                "improvement": round(float(corr_ba - lag0), 4),
                "type": "lead-lag",
                "method": "smoothed",
                "category": kw_to_cat.get(kw_b, "unknown"),
            })

        if corr_ab >= CORRELATION_THRESHOLD and lag_ab > 0:
            lag0 = all_corrs_ab.get(0, 0)
            smooth_results.append({
                "leader": kw_a,
                "follower": kw_b,
                "lag_days": int(lag_ab),
                "correlation": round(float(corr_ab), 4),
                "lag0_correlation": round(float(lag0), 4),
                "improvement": round(float(corr_ab - lag0), 4),
                "type": "lead-lag",
                "method": "smoothed",
                "category": kw_to_cat.get(kw_a, "unknown"),
            })

    # ── Pass 2: Differenced series for short-term change leadership ──
    print("  Pass 2: Differenced series — change-leadership detection")
    diff_pivot = pivot.diff().dropna()

    diff_results = []
    for kw_a, kw_b in combinations(keywords, 2):
        common = diff_pivot[[kw_a, kw_b]].dropna()
        if len(common) < 20:
            continue

        # b leads a (b's change today → a's change later)
        lag_ba, corr_ba, all_corrs_ba = cross_correlate(common[kw_b], common[kw_a], min(30, len(common) // 2))
        # a leads b
        lag_ab, corr_ab, all_corrs_ab = cross_correlate(common[kw_a], common[kw_b], min(30, len(common) // 2))

        if corr_ba >= DIFF_THRESHOLD and lag_ba > 0:
            lag0 = all_corrs_ba.get(0, 0)
            diff_results.append({
                "leader": kw_b,
                "follower": kw_a,
                "lag_days": int(lag_ba),
                "correlation": round(float(corr_ba), 4),
                "lag0_correlation": round(float(lag0), 4),
                "improvement": round(float(corr_ba - lag0), 4),
                "type": "lead-lag",
                "method": "differenced",
                "category": kw_to_cat.get(kw_b, "unknown"),
            })

        if corr_ab >= DIFF_THRESHOLD and lag_ab > 0:
            lag0 = all_corrs_ab.get(0, 0)
            diff_results.append({
                "leader": kw_a,
                "follower": kw_b,
                "lag_days": int(lag_ab),
                "correlation": round(float(corr_ab), 4),
                "lag0_correlation": round(float(lag0), 4),
                "improvement": round(float(corr_ab - lag0), 4),
                "type": "lead-lag",
                "method": "differenced",
                "category": kw_to_cat.get(kw_a, "unknown"),
            })

    # ── Pass 3: Raw concurrent correlations for context ──
    print("  Pass 3: Raw series — concurrent high correlations")
    raw_results = []
    for kw_a, kw_b in combinations(keywords, 2):
        common = pivot[[kw_a, kw_b]].dropna()
        if len(common) < 30:
            continue
        corr = np.corrcoef(common[kw_a], common[kw_b])[0, 1]
        if not np.isnan(corr) and abs(corr) >= 0.85:
            raw_results.append({
                "leader": kw_a,
                "follower": kw_b,
                "lag_days": 0,
                "correlation": round(float(corr), 4),
                "type": "concurrent",
                "method": "raw",
                "category": kw_to_cat.get(kw_a, "unknown"),
            })

    raw_results.sort(key=lambda x: x["correlation"], reverse=True)

    # ── Merge and deduplicate ──
    # Prioritize lead-lag pairs (smoothed and differenced), then concurrent
    seen_pairs = set()
    final_results = []

    # Lead-lag from smoothed (best quality)
    smooth_results.sort(key=lambda x: -x["improvement"])
    for r in smooth_results:
        key = (r["leader"], r["follower"])
        if key not in seen_pairs:
            seen_pairs.add(key)
            final_results.append(r)

    # Lead-lag from differenced
    diff_results.sort(key=lambda x: -x["improvement"])
    for r in diff_results:
        key = (r["leader"], r["follower"])
        if key not in seen_pairs:
            seen_pairs.add(key)
            final_results.append(r)

    # Concurrent for remaining slots
    for r in raw_results:
        key = (r["leader"], r["follower"])
        if key not in seen_pairs:
            seen_pairs.add(key)
            final_results.append(r)

    final_results = final_results[:TOP_N]

    # Stats
    smooth_count = sum(1 for r in final_results if r.get("method") == "smoothed")
    diff_count = sum(1 for r in final_results if r.get("method") == "differenced")
    concurrent_count = sum(1 for r in final_results if r.get("method") == "raw")

    print(f"\n  Results: {smooth_count} smoothed, {diff_count} differenced, {concurrent_count} concurrent")
    print(f"  Total lead-lag pairs saved: {len(final_results)}")

    if smooth_count > 0:
        print(f"\n  🔮 Medium-term lead-lag (smoothed):")
        for r in [x for x in final_results if x.get("method") == "smoothed"][:10]:
            print(f"    {r['leader']:30s} → {r['follower']:30s} "
                  f"lag={r['lag_days']:3d}d  r={r['correlation']:.3f}  (Δ={r['improvement']:+.3f})")

    if diff_count > 0:
        print(f"\n  ⚡ Short-term change leadership (differenced):")
        for r in [x for x in final_results if x.get("method") == "differenced"][:10]:
            print(f"    {r['leader']:30s} → {r['follower']:30s} "
                  f"lag={r['lag_days']:3d}d  r={r['correlation']:.3f}  (Δ={r['improvement']:+.3f})")

    if concurrent_count > 0:
        print(f"\n  ⟷  Concurrent (same-day):")
        for r in [x for x in final_results if x.get("method") == "raw"][:5]:
            print(f"    {r['leader']:30s} ↔ {r['follower']:30s}  r={r['correlation']:.3f}")

    with open(OUTPUT, "w") as f:
        json.dump(final_results, f, indent=2)

    print(f"\n  ✓ Saved {len(final_results)} pairs to {OUTPUT}")
    return final_results


if __name__ == "__main__":
    run_lead_lag()
