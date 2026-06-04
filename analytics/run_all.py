#!/usr/bin/env python3
"""
Analytics Orchestrator — Run all analytics modules and print summary.
Usage: python analytics/run_all.py
"""

import sys
import time
from pathlib import Path

# Ensure we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.lead_lag import run_lead_lag
from analytics.seasonal_forecaster import run_seasonal
from analytics.anomaly_detection import run_anomalies
from analytics.correlation_matrix import run_correlation_matrix


def main():
    start = time.time()

    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + "  🐕 DOG TREND RADAR — ANALYTICS ENGINE".center(58) + "║")
    print("╚" + "═" * 58 + "╝")

    modules = [
        ("Lead-Lag Correlation", run_lead_lag),
        ("Seasonal Forecaster", run_seasonal),
        ("Anomaly Detection", run_anomalies),
        ("Correlation Matrix", run_correlation_matrix),
    ]

    results = {}
    for name, func in modules:
        t0 = time.time()
        try:
            result = func()
            elapsed = time.time() - t0
            results[name] = {"status": "✓", "time": elapsed, "result": result}
        except Exception as e:
            elapsed = time.time() - t0
            results[name] = {"status": "✗", "time": elapsed, "error": str(e)}
            print(f"\n  ❌ {name} FAILED: {e}")

    # ── Summary ──
    total = time.time() - start
    print()
    print("═" * 60)
    print("  SUMMARY")
    print("═" * 60)

    for name, info in results.items():
        icon = "✅" if info["status"] == "✓" else "❌"
        print(f"  {icon} {name:<25s}  {info['time']:.1f}s  [{info['status']}]")

    print(f"\n  ⏱  Total: {total:.1f}s")
    print(f"  📁 Outputs in data/:")
    for fname in ["lead_lag_pairs.json", "seasonal_forecasts.json", "anomalies.json", "correlation_matrix.json"]:
        path = Path(__file__).parent.parent / "data" / fname
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"    • {fname} ({size_kb:.1f} KB)")

    # Count key findings
    lead_lag = results.get("Lead-Lag Correlation", {}).get("result", [])
    anomalies = results.get("Anomaly Detection", {}).get("result", [])

    print(f"\n  📊 Key findings:")
    print(f"    • {len(lead_lag)} significant lead-lag pairs detected")
    print(f"    • {len(anomalies)} anomalies flagged (z > 2.5σ)")

    return 0 if all(v["status"] == "✓" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
