#!/usr/bin/env python3
"""
Dog Trend Radar — Unified Pipeline
Runs EVERYTHING in order: scrapers → analytics → summary → briefing
Then auto-commits + pushes to GitHub if --deploy flag is set.

Usage:
    python3 pipeline.py              # Run everything
    python3 pipeline.py --deploy     # Run + git push
    python3 pipeline.py --skip-scrape  # Only analytics + briefing
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

STAGE_SCRIPTS = {
    "scrapers": [
        "scrapers/reddit_scraper.py",
        "scrapers/amazon_scraper.py",
        "scrapers/kickstarter_scraper.py",
        "scrapers/uspto_scraper.py",
        "scrapers/crunchbase_scraper.py",
        "scrapers/vet_conference_scraper.py",
        "scrapers/retail_scraper.py",
        "scrapers/tiktok_scraper.py",
    ],
    "google_trends": ["trend_scraper.py"],
    "analytics": [
        "analytics/lead_lag.py",
        "analytics/seasonal_forecaster.py",
        "analytics/anomaly_detection.py",
        "analytics/correlation_matrix.py",
    ],
}

def run_script(script_path):
    """Run a Python script and return (success, elapsed_seconds)."""
    full_path = ROOT / script_path
    if not full_path.exists():
        print(f"  ⚠ {script_path} not found, skipping")
        return False, 0

    start = time.time()
    print(f"\n{'─'*50}")
    print(f"  ▶ {script_path}")
    print(f"{'─'*50}")

    try:
        result = subprocess.run(
            [sys.executable, str(full_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        elapsed = time.time() - start

        if result.stdout:
            # Print last 20 lines for brevity
            lines = result.stdout.strip().split("\n")
            if len(lines) > 20:
                print("\n".join(lines[-20:]))
                print(f"  ... ({len(lines)} lines total)")
            else:
                print(result.stdout)

        if result.returncode == 0:
            print(f"  ✅ {script_path} ({elapsed:.1f}s)")
            return True, elapsed
        else:
            print(f"  ❌ {script_path} failed (exit {result.returncode})")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
            return False, elapsed

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"  ⏰ {script_path} timed out after 300s")
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"  💥 {script_path} error: {e}")
        return False, elapsed


def generate_pipeline_summary(stage_results):
    """Generate a pipeline summary JSON."""
    data_files = sorted(DATA_DIR.glob("*.json"))
    data_sizes = {}
    for f in data_files:
        try:
            data_sizes[f.name] = f.stat().st_size
        except OSError:
            data_sizes[f.name] = 0

    return {
        "pipeline_run_at": datetime.now(timezone.utc).isoformat(),
        "stages": stage_results,
        "data_files": data_sizes,
    }


def print_briefing():
    """Print a quick briefing from the collected data."""
    print(f"\n{'='*60}")
    print("  📋 DOG TREND RADAR — BRIEFING")
    print(f"  {datetime.now().strftime('%B %d, %Y %I:%M %p MST')}")
    print(f"{'='*60}")

    # Trend movers
    try:
        summary = json.loads((DATA_DIR / "summary.json").read_text())
        movers = summary.get("trend_movers", [])
        if movers:
            print("\n📈 TOP TREND MOVERS (30-day):")
            for m in movers[:8]:
                d = "▲" if m["change_pct"] > 0 else "▼"
                print(f"  {d} {m['change_pct']:+.1f}% {m['keyword']} ({m['category']})")
    except Exception:
        pass

    # Lead-lag predictions
    try:
        ll = json.loads((DATA_DIR / "lead_lag_pairs.json").read_text())
        if ll:
            print("\n🔮 LEAD-LAG PREDICTIONS:")
            for pair in ll[:5]:
                print(f"  {pair['leader']} → {pair['follower']} ({pair['lag_days']}d lag, r={pair['correlation']:.2f})")
    except Exception:
        pass

    # Anomalies
    try:
        anom = json.loads((DATA_DIR / "anomalies.json").read_text())
        anomalies = anom.get("anomalies", [])
        if anomalies:
            print("\n⚡ ANOMALIES:")
            for a in anomalies[:5]:
                print(f"  {a['keyword']}: z={a['z_score']:.1f} on {a.get('date', '?')}")
    except Exception:
        pass

    # Reddit buzz
    try:
        reddit = json.loads((DATA_DIR / "reddit_signals.json").read_text())
        subreddits = reddit.get("subreddits", {})
        all_kws = []
        for sr, data in subreddits.items():
            all_kws.extend(data.get("top_keywords", []))
        all_kws.sort(key=lambda x: x["count"], reverse=True)
        if all_kws:
            print("\n📱 REDDIT BUZZ:")
            for kw in all_kws[:5]:
                print(f"  #{kw['term']} ({kw['count']} mentions)")
    except Exception:
        pass

    # Product watch
    try:
        amazon = json.loads((DATA_DIR / "amazon_signals.json").read_text())
        movers = amazon.get("movers", [])
        gainers = [m for m in movers if m.get("change_pct", 0) > 0]
        gainers.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        if gainers:
            print("\n🛒 AMAZON MOVERS (Pet Supplies):")
            for m in gainers[:5]:
                print(f"  ▲ +{m.get('change_pct', '?')}% {m.get('title', m.get('name', '?'))}")
    except Exception:
        pass

    print(f"\n{'='*60}")


def deploy():
    """Git add, commit, push."""
    print("\n🚀 Deploying to GitHub...")
    try:
        subprocess.run(["git", "add", "-A"], cwd=str(ROOT), check=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"data update: {timestamp}"],
            cwd=str(ROOT), check=False, capture_output=True,
        )
        subprocess.run(["git", "push"], cwd=str(ROOT), check=True, timeout=60)
        print("✅ Pushed to GitHub — dashboard will update in ~60s")
        return True
    except Exception as e:
        print(f"❌ Deploy failed: {e}")
        return False


def main():
    skip_scrape = "--skip-scrape" in sys.argv
    do_deploy = "--deploy" in sys.argv

    print(f"{'='*60}")
    print(f"  🐕 DOG TREND RADAR — UNIFIED PIPELINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"{'='*60}")

    total_start = time.time()
    stage_results = {}

    if not skip_scrape:
        # Stage 1: All external scrapers
        print("\n📡 STAGE 1: External Scrapers")
        scraper_results = {}
        for script in STAGE_SCRIPTS["scrapers"]:
            ok, elapsed = run_script(script)
            scraper_results[script] = {"ok": ok, "elapsed": round(elapsed, 1)}
        stage_results["scrapers"] = scraper_results

        # Stage 2: Google Trends
        print("\n📊 STAGE 2: Google Trends")
        for script in STAGE_SCRIPTS["google_trends"]:
            ok, elapsed = run_script(script)
            stage_results["google_trends"] = {"ok": ok, "elapsed": round(elapsed, 1)}

    # Stage 3: Analytics
    print("\n🧠 STAGE 3: Analytics")
    analytics_results = {}
    for script in STAGE_SCRIPTS["analytics"]:
        ok, elapsed = run_script(script)
        analytics_results[script] = {"ok": ok, "elapsed": round(elapsed, 1)}
    stage_results["analytics"] = analytics_results

    # Pipeline summary
    pipeline_summary = generate_pipeline_summary(stage_results)
    with open(DATA_DIR / "pipeline_summary.json", "w") as f:
        json.dump(pipeline_summary, f, indent=2, default=str)

    total_elapsed = time.time() - total_start
    ok_count = sum(
        1 for stage in stage_results.values()
        for result in (stage.values() if isinstance(stage, dict) else [stage])
        if isinstance(result, dict) and result.get("ok")
    )
    total_scripts = sum(
        len(stage) if isinstance(stage, dict) else 1
        for stage in stage_results.values()
    )

    print(f"\n{'='*60}")
    print(f"  📊 PIPELINE COMPLETE")
    print(f"  {ok_count}/{total_scripts} scripts passed in {total_elapsed:.0f}s")
    print(f"{'='*60}")

    # Merge dashboard files
    merge_dashboard_files()

    # Print briefing
    print_briefing()

    # Deploy if requested
    if do_deploy:
        deploy()

    print(f"\n📊 Dashboard: https://theastark1-cpu.github.io/dog-trend-radar/")


def merge_dashboard_files():
    """Merge individual scraped files into the combined files the dashboard expects."""
    print("\n📦 Merging dashboard data files...")

    # reddit.json
    src = DATA_DIR / "reddit_signals.json"
    if src.exists():
        import shutil
        shutil.copy(src, DATA_DIR / "reddit.json")
        print("  ✓ reddit.json")

    # products.json (amazon + retail + kickstarter)
    products = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "amazon": {"movers": [], "total": 0},
        "retail": {"new_products": [], "total": 0},
        "kickstarter": {"projects": [], "total": 0},
    }
    for key, src_name in [("amazon", "amazon_signals.json"), ("retail", "retail_signals.json"), ("kickstarter", "kickstarter_signals.json")]:
        src = DATA_DIR / src_name
        if src.exists():
            try:
                data = json.loads(src.read_text())
                if key == "amazon":
                    products["amazon"] = {"movers": data.get("movers", data.get("products", [])), "total": data.get("total", len(data.get("movers", data.get("products", []))))}
                elif key == "retail":
                    products["retail"] = {"new_products": data.get("new_products", []), "total": data.get("total", 0)}
                elif key == "kickstarter":
                    products["kickstarter"] = {"projects": data.get("projects", []), "total": data.get("total_unique", 0)}
            except Exception as e:
                print(f"  ⚠ {src_name}: {e}")
    with open(DATA_DIR / "products.json", "w") as f:
        json.dump(products, f, indent=2)
    print(f"  ✓ products.json (A:{products['amazon']['total']} R:{products['retail']['total']} KS:{products['kickstarter']['total']})")

    # signals.json (crunchbase + uspto + vet + tiktok)
    signals = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "crunchbase": {"funding_rounds": [], "total": 0},
        "uspto": {"patents": [], "total": 0},
        "vet_conferences": {"conferences": [], "total": 0, "emerging_themes": []},
        "tiktok": {"hashtags": [], "total_tracked": 0, "emerging_trends": []},
    }
    for key, src_name in [("crunchbase", "crunchbase_signals.json"), ("uspto", "uspto_signals.json"), ("vet_conferences", "vet_conference_signals.json"), ("tiktok", "tiktok_signals.json")]:
        src = DATA_DIR / src_name
        if src.exists():
            try:
                data = json.loads(src.read_text())
                if key == "crunchbase":
                    signals["crunchbase"] = {"funding_rounds": data.get("funding_rounds", []), "total": data.get("total", 0)}
                elif key == "uspto":
                    signals["uspto"] = {"patents": data.get("patents", []), "total": data.get("total_unique", 0)}
                elif key == "vet_conferences":
                    signals["vet_conferences"] = {"conferences": data.get("conferences", []), "total": data.get("total", 0), "emerging_themes": data.get("emerging_themes", [])}
                elif key == "tiktok":
                    signals["tiktok"] = {"hashtags": data.get("hashtags", []), "total_tracked": data.get("total_tracked", 0), "emerging_trends": data.get("emerging_trends", [])}
            except Exception as e:
                print(f"  ⚠ {src_name}: {e}")
    with open(DATA_DIR / "signals.json", "w") as f:
        json.dump(signals, f, indent=2)
    print(f"  ✓ signals.json (CB:{signals['crunchbase']['total']} USPTO:{signals['uspto']['total']} Vet:{signals['vet_conferences']['total']} TT:{signals['tiktok']['total_tracked']})")

    print("  ✅ Dashboard files merged")


if __name__ == "__main__":
    main()
