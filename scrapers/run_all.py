#!/usr/bin/env python3
"""Run all dog trend radar scrapers sequentially and print a combined summary.

Usage: python3 scrapers/run_all.py
"""

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCRAPERS = [
    ("reddit", "reddit_scraper"),
    ("amazon", "amazon_scraper"),
    ("kickstarter", "kickstarter_scraper"),
    ("uspto", "uspto_scraper"),
    ("crunchbase", "crunchbase_scraper"),
    ("vet_conference", "vet_conference_scraper"),
    ("retail", "retail_scraper"),
    ("tiktok", "tiktok_scraper"),
]


def run_scraper(module_name):
    """Run a single scraper module and return results summary."""
    import importlib
    start = time.time()
    try:
        module = importlib.import_module(f"scrapers.{module_name}")
        module.main()
        elapsed = time.time() - start
        return {"status": "success", "elapsed_sec": round(elapsed, 1)}
    except Exception as e:
        elapsed = time.time() - start
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_sec": round(elapsed, 1),
        }


def load_output_stats(name):
    """Load stats from a scraper's output JSON file."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    filename = f"{name}_signals.json"
    filepath = data_dir / filename

    if not filepath.exists():
        return {"file": filename, "exists": False}

    try:
        with open(filepath) as f:
            data = json.load(f)

        stats = {"file": filename, "exists": True, "size_kb": round(filepath.stat().st_size / 1024, 1)}

        # Extract key counts based on scraper type
        if name == "reddit":
            total_posts = sum(len(v.get("posts", [])) for v in data.get("subreddits", {}).values())
            stats["posts"] = total_posts
            stats["subreddits"] = len(data.get("subreddits", {}))
        elif name == "amazon":
            stats["products"] = len(data.get("products", []))
        elif name == "kickstarter":
            stats["projects"] = data.get("total_unique", len(data.get("projects", [])))
        elif name == "uspto":
            stats["patents"] = data.get("total_unique", len(data.get("patents", [])))
        elif name == "crunchbase":
            stats["funding_rounds"] = data.get("total", len(data.get("funding_rounds", [])))
        elif name == "vet_conference":
            stats["conferences"] = len(data.get("conferences", []))
            stats["upcoming"] = len(data.get("known_upcoming_conferences", []))
        elif name == "retail":
            stats["products"] = data.get("total_products_found", 0)
            stats["sources"] = len(data.get("sources", []))
        elif name == "tiktok":
            stats["hashtags"] = data.get("total_tracked", len(data.get("hashtags", [])))

        return stats
    except Exception as e:
        return {"file": filename, "exists": True, "error": str(e)}


def main():
    print("=" * 60)
    print("🐕 DOG TREND RADAR - Run All Scrapers")
    print("=" * 60)
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"Scrapers to run: {len(SCRAPERS)}")
    print()

    results = {}
    total_start = time.time()

    for i, (name, module_name) in enumerate(SCRAPERS, 1):
        print(f"[{i}/{len(SCRAPERS)}] Running {name} scraper ({module_name}.py)...")
        print("-" * 40)

        result = run_scraper(module_name)
        results[name] = result

        if result["status"] == "success":
            print(f"  ✅ Completed in {result['elapsed_sec']}s")
        else:
            print(f"  ❌ FAILED: {result['error']}")
        print()

    total_elapsed = time.time() - total_start

    # Print combined summary
    print("=" * 60)
    print("📊 COMBINED SUMMARY")
    print("=" * 60)

    success_count = sum(1 for r in results.values() if r["status"] == "success")
    fail_count = sum(1 for r in results.values() if r["status"] != "success")

    print(f"Total time: {total_elapsed:.1f}s")
    print(f"Successful: {success_count}/{len(SCRAPERS)}")
    print(f"Failed: {fail_count}/{len(SCRAPERS)}")
    print()

    # Load and display data stats for each scraper
    print("Output files:")
    data_dir = Path(__file__).resolve().parent.parent / "data"
    for name, _ in SCRAPERS:
        status = "✅" if results[name]["status"] == "success" else "❌"
        stats = load_output_stats(name)
        stat_str = ", ".join(f"{k}={v}" for k, v in stats.items() if k not in ("file", "exists", "size_kb"))
        print(f"  {status} {name:20s} | {stats.get('size_kb', '?'):5} KB | {stat_str}")

    # Write summary
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_sec": round(total_elapsed, 1),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
        "data_snapshots": {
            name: load_output_stats(name) for name, _ in SCRAPERS
        },
    }

    summary_file = data_dir / "run_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n📝 Summary saved to {summary_file}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
