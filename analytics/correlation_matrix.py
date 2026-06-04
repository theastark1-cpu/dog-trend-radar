#!/usr/bin/env python3
"""
Correlation Matrix Generator
Creates a keyword × keyword correlation matrix for the dashboard.
Uses Pearson correlation on the aligned time series.
Output: {keywords: [...], matrix: [[float, ...], ...]}
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT = DATA_DIR / "correlation_matrix.json"
ALL_TRENDS = DATA_DIR / "all_trends.csv"


def build_correlation_matrix(pivot):
    """
    Compute Pearson correlation matrix between all keyword pairs.
    Returns {keywords, matrix, categories, top_pairs}.
    """
    # Compute correlation matrix
    corr_matrix = pivot.corr(method="pearson")

    keywords = list(corr_matrix.columns)
    n = len(keywords)

    # Convert to list-of-lists for JSON
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            val = corr_matrix.iloc[i, j]
            row.append(round(float(val), 4) if not np.isnan(val) else 0.0)
        matrix.append(row)

    # Find top correlated pairs (excluding self-correlations)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            val = corr_matrix.iloc[i, j]
            if not np.isnan(val):
                pairs.append({
                    "keyword_a": keywords[i],
                    "keyword_b": keywords[j],
                    "correlation": round(float(val), 4),
                })

    # Sort by absolute correlation
    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    # Top positive and negative pairs
    positive_pairs = [p for p in pairs if p["correlation"] > 0]
    negative_pairs = [p for p in pairs if p["correlation"] < 0]

    return keywords, matrix, pairs, positive_pairs, negative_pairs


def run_correlation_matrix():
    """Main entry point."""
    print("=" * 60)
    print("  CORRELATION MATRIX GENERATOR")
    print("=" * 60)

    df = pd.read_csv(ALL_TRENDS)
    df["date"] = pd.to_datetime(df["date"])

    # Build keyword → category mapping
    kw_to_cat = {}
    cat_to_keywords = {}
    for _, row in df.iterrows():
        kw_to_cat[row["keyword"]] = row["category"]
        cat_to_keywords.setdefault(row["category"], set()).add(row["keyword"])

    pivot = df.pivot_table(
        index="date", columns="keyword", values="interest", aggfunc="mean"
    ).sort_index()

    # Fill missing with forward fill then backward fill for edge gaps
    pivot = pivot.ffill().bfill()
    pivot = pivot.dropna(axis=1, how="all")

    keywords, matrix, all_pairs, positive_pairs, negative_pairs = build_correlation_matrix(pivot)

    print(f"  Keywords: {len(keywords)}")
    print(f"  Pairs: {len(all_pairs)}")

    # Category breakdown
    for cat, kws in sorted(cat_to_keywords.items()):
        present = [k for k in kws if k in keywords]
        print(f"    {cat}: {len(present)} keywords")

    # Top correlations
    print(f"\n  🔗 Top positive correlations:")
    for p in positive_pairs[:10]:
        print(f"    {p['keyword_a']:30s} ↔ {p['keyword_b']:30s}  r={p['correlation']:.3f}")

    if negative_pairs:
        print(f"\n  ⚡ Top negative correlations:")
        for p in negative_pairs[:5]:
            print(f"    {p['keyword_a']:30s} ↔ {p['keyword_b']:30s}  r={p['correlation']:.3f}")

    # Summary stats
    corr_values = [p["correlation"] for p in all_pairs]
    print(f"\n  Matrix stats: mean={np.mean(corr_values):.3f}, "
          f"median={np.median(corr_values):.3f}, "
          f"range=[{min(corr_values):.3f}, {max(corr_values):.3f}]")

    output = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "method": "pearson",
        "num_keywords": len(keywords),
        "keywords": keywords,
        "matrix": matrix,
        "categories": {kw: kw_to_cat.get(kw, "unknown") for kw in keywords},
        "top_correlated_pairs": all_pairs[:20],
        "stats": {
            "mean_correlation": round(float(np.mean(corr_values)), 4),
            "median_correlation": round(float(np.median(corr_values)), 4),
            "min_correlation": round(float(min(corr_values)), 4),
            "max_correlation": round(float(max(corr_values)), 4),
            "positive_pairs_count": len(positive_pairs),
            "negative_pairs_count": len(negative_pairs),
        },
    }

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  ✓ Saved to {OUTPUT}")
    return output


if __name__ == "__main__":
    run_correlation_matrix()
