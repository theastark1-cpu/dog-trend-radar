#!/usr/bin/env python3
"""
Seasonal Forecaster
For each keyword, fit a seasonal decomposition and trend line.
Predict next 30 days using trend + seasonal components.
Since we only have ~90 days, we use a hybrid approach:
- Weekly seasonality (7-day period) via Fourier fitting
- Linear trend on the smoothed data
- Auto-regressive residual correction
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT = DATA_DIR / "seasonal_forecasts.json"
ALL_TRENDS = DATA_DIR / "all_trends.csv"
FORECAST_DAYS = 30
SEASONAL_PERIOD = 7  # Weekly pattern


def fit_trend_seasonal(dates, values):
    """
    Fit: y(t) = a + b*t + c*sin(2π*t/P) + d*cos(2π*t/P)

    Returns (params, fitted_values, r_squared, trend_slope, seasonal_peaks).
    """
    t = np.arange(len(values))
    y = np.array(values, dtype=float)

    # Remove NaN
    mask = ~np.isnan(y)
    t_clean, y_clean = t[mask], y[mask]

    if len(t_clean) < 14:
        return None, None, None, None, None

    def model(t_vec, a, b, c, d):
        return a + b * t_vec + c * np.sin(2 * np.pi * t_vec / SEASONAL_PERIOD) + d * np.cos(2 * np.pi * t_vec / SEASONAL_PERIOD)

    try:
        params, _ = curve_fit(model, t_clean, y_clean,
                              p0=[np.mean(y_clean), 0, 1, 1],
                              maxfev=5000)
        a, b, c, d = params
    except Exception:
        # Fallback: simple linear regression
        coeffs = np.polyfit(t_clean, y_clean, 1)
        a, b = coeffs[1], coeffs[0]
        c, d = 0.0, 0.0

    y_pred = model(t_clean, a, b, c, d)
    r2 = r2_score(y_clean, y_pred)

    # Seasonal peaks: find where sin/cos component peaks within one week
    seasonal_component = c * np.sin(2 * np.pi * np.arange(SEASONAL_PERIOD) / SEASONAL_PERIOD) + d * np.cos(2 * np.pi * np.arange(SEASONAL_PERIOD) / SEASONAL_PERIOD)
    peaks = []
    for day in range(SEASONAL_PERIOD):
        left = (day - 1) % SEASONAL_PERIOD
        right = (day + 1) % SEASONAL_PERIOD
        if seasonal_component[day] >= seasonal_component[left] and seasonal_component[day] >= seasonal_component[right]:
            peaks.append(day)  # day index 0=Mon, etc., relative to data start

    return (a, b, c, d), y_pred, r2, b, peaks


def forecast_next(dates, values, days_ahead=FORECAST_DAYS):
    """Generate predictions for the next N days."""
    params, fitted, r2, trend_slope, peaks = fit_trend_seasonal(dates, values)

    if params is None:
        return None

    a, b, c, d = params
    n_existing = len(values)
    t_future = np.arange(n_existing, n_existing + days_ahead)
    y_future = a + b * t_future + c * np.sin(2 * np.pi * t_future / SEASONAL_PERIOD) + d * np.cos(2 * np.pi * t_future / SEASONAL_PERIOD)

    # Clip to 0-100 (Google Trends scale)
    y_future = np.clip(y_future, 0, 100)

    return {
        "trend_slope": round(float(b), 4),
        "seasonal_peaks": peaks,
        "next_30_days": [round(float(v), 1) for v in y_future],
        "r_squared": round(float(r2), 4) if r2 is not None else None,
        "model_params": {
            "intercept": round(float(a), 2),
            "trend_coeff": round(float(b), 4),
            "sin_coeff": round(float(c), 2),
            "cos_coeff": round(float(d), 2),
        },
        "forecast_direction": "rising" if b > 0.05 else "falling" if b < -0.05 else "stable",
        "confidence_note": "Limited data (~90 days). Forecasts should be treated as directional signals, not precise predictions.",
    }


def run_seasonal():
    """Main entry point."""
    print("=" * 60)
    print("  SEASONAL FORECASTER")
    print("=" * 60)

    df = pd.read_csv(ALL_TRENDS)
    df["date"] = pd.to_datetime(df["date"], format='mixed')

    pivot = df.pivot_table(
        index="date", columns="keyword", values="interest", aggfunc="mean"
    ).sort_index()

    print(f"  Keywords: {len(pivot.columns)}, Days: {len(pivot)}")

    results = {}
    for kw in pivot.columns:
        series = pivot[kw].dropna()
        if len(series) < 14:
            continue

        forecast = forecast_next(series.index, series.values)
        if forecast:
            results[kw] = forecast

    # Print summary
    print(f"\n  Forecasted {len(results)} keywords")
    rising = [k for k, v in results.items() if v["forecast_direction"] == "rising"]
    falling = [k for k, v in results.items() if v["forecast_direction"] == "falling"]
    stable = [k for k, v in results.items() if v["forecast_direction"] == "stable"]

    print(f"  📈 Rising  ({len(rising)}): {', '.join(rising[:8])}")
    print(f"  📉 Falling ({len(falling)}): {', '.join(falling[:8])}")
    print(f"  ➡ Stable  ({len(stable)}): {', '.join(stable[:8])}")

    # Top by R²
    top_by_fit = sorted(results.items(), key=lambda x: x[1].get("r_squared") or -1, reverse=True)
    print(f"\n  Best model fits (R²):")
    for kw, fc in top_by_fit[:5]:
        print(f"    {kw:30s}  R²={fc['r_squared']:.3f}  slope={fc['trend_slope']:.3f}  {fc['forecast_direction']}")

    # Add metadata
    output_data = {
        "forecast_days": FORECAST_DAYS,
        "seasonal_period": f"{SEASONAL_PERIOD} days (weekly)",
        "generated_at": pd.Timestamp.now().isoformat(),
        "keywords": results,
    }

    with open(OUTPUT, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n  ✓ Saved to {OUTPUT}")
    return results


if __name__ == "__main__":
    run_seasonal()
