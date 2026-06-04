#!/usr/bin/env python3
"""
Anomaly Detection Engine
For each keyword, compare the last 14 days to historical normal range.
Flags values > 2.5 standard deviations from the mean.
Uses rolling 90-day window as baseline (since we have ~90 days of data).
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT = DATA_DIR / "anomalies.json"
ALL_TRENDS = DATA_DIR / "all_trends.csv"
RECENT_WINDOW = 14
ROLLING_WINDOW = 90
Z_THRESHOLD = 2.5


def detect_anomalies(series, dates):
    """
    Detect anomalies in a keyword's time series.
    Uses rolling 90-day mean/std as baseline.
    Returns list of anomalous data points.
    """
    values = series.values.astype(float)
    n = len(values)

    if n < ROLLING_WINDOW:
        return [], None

    anomalies = []
    all_z_scores = []

    for i in range(n - RECENT_WINDOW, n):
        # Rolling window: use the 90 days before the current point
        start = max(0, i - ROLLING_WINDOW)
        window = values[start:i]

        if len(window) < 14:  # Need enough data for meaningful statistics
            continue

        mean = np.mean(window)
        std = np.std(window)

        if std < 0.5:  # Avoid division by zero / near-constant series
            continue

        z_score = (values[i] - mean) / std
        all_z_scores.append({"date": str(dates.iloc[i].date()), "value": float(values[i]), "z_score": round(float(z_score), 3)})

        if abs(z_score) >= Z_THRESHOLD:
            direction = "spike" if z_score > 0 else "dip"
            anomalies.append({
                "keyword": series.name,
                "date": str(dates.iloc[i].date()),
                "value": float(values[i]),
                "z_score": round(float(z_score), 3),
                "direction": direction,
                "baseline_mean": round(float(mean), 2),
                "baseline_std": round(float(std), 2),
                "threshold": round(float(mean + Z_THRESHOLD * std), 2) if z_score > 0 else round(float(mean - Z_THRESHOLD * std), 2),
            })

    # Compute overall volatility stats
    if len(all_z_scores) > 0:
        avg_abs_z = np.mean([abs(z["z_score"]) for z in all_z_scores])
        max_z = max(abs(z["z_score"]) for z in all_z_scores)
        stats = {
            "recent_avg_abs_z": round(float(avg_abs_z), 3),
            "recent_max_abs_z": round(float(max_z), 3),
            "recent_volatile": bool(avg_abs_z > 1.0),
        }
    else:
        stats = None

    return anomalies, stats


def run_anomalies():
    """Main entry point."""
    print("=" * 60)
    print("  ANOMALY DETECTION")
    print("=" * 60)

    df = pd.read_csv(ALL_TRENDS)
    df["date"] = pd.to_datetime(df["date"], format='mixed')

    pivot = df.pivot_table(
        index="date", columns="keyword", values="interest", aggfunc="mean"
    ).sort_index()

    # Forward fill small gaps
    pivot = pivot.ffill().bfill()

    print(f"  Keywords: {len(pivot.columns)}, Days: {len(pivot)}")
    print(f"  Recent window: {RECENT_WINDOW} days, Z-threshold: {Z_THRESHOLD}σ")
    print(f"  Baseline: rolling {ROLLING_WINDOW}-day mean/std")

    all_anomalies = []
    keyword_stats = {}

    for kw in pivot.columns:
        series = pivot[kw].dropna()
        if len(series) < 30:
            continue

        anomalies, stats = detect_anomalies(series, pd.Series(pivot.index, index=pivot.index))
        if anomalies:
            all_anomalies.extend(anomalies)
        if stats:
            keyword_stats[kw] = stats

    # Sort anomalies by absolute z_score
    all_anomalies.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    print(f"\n  Detected {len(all_anomalies)} anomalies across {len(keyword_stats)} keywords")

    # Print flagged anomalies
    if all_anomalies:
        print("\n  ⚠️  Flagged anomalies (z > {:.1f}σ):".format(Z_THRESHOLD))
        spikes = [a for a in all_anomalies if a["direction"] == "spike"]
        dips = [a for a in all_anomalies if a["direction"] == "dip"]
        for a in all_anomalies[:20]:
            icon = "🔺" if a["direction"] == "spike" else "🔻"
            print(f"    {icon} {a['keyword']:30s} | {a['date']} | "
                  f"z={a['z_score']:+6.2f} | value={a['value']:.0f} "
                  f"(expected {a['baseline_mean']:.0f}±{a['baseline_std']:.0f})")

    # Most volatile keywords
    volatile = [(k, v) for k, v in keyword_stats.items() if v["recent_volatile"]]
    volatile.sort(key=lambda x: x[1]["recent_avg_abs_z"], reverse=True)
    if volatile:
        print("\n  🌊 Most volatile keywords (recent |z| avg > 1.0):")
        for kw, s in volatile[:10]:
            print(f"    {kw:30s}  avg|z|={s['recent_avg_abs_z']:.2f}  max|z|={s['recent_max_abs_z']:.2f}")

    output = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "parameters": {
            "recent_window_days": RECENT_WINDOW,
            "rolling_baseline_days": ROLLING_WINDOW,
            "z_threshold": Z_THRESHOLD,
        },
        "total_anomalies": len(all_anomalies),
        "anomalies": all_anomalies,
        "keyword_volatility": keyword_stats,
    }

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  ✓ Saved to {OUTPUT}")
    return all_anomalies


if __name__ == "__main__":
    run_anomalies()
