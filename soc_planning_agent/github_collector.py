"""Standalone collector for GitHub Actions.

Runs in GitHub Actions (full internet access, no proxy restrictions).
Fetches RSS → filters by keyword → summarizes with Claude Haiku → writes JSON.

Output: soc_planning_agent/data/YYYY-MM-DD.json
This file is committed to the repo; local agent imports it with:
  python main.py sync

Usage (GitHub Actions):
  pip install anthropic
  python soc_planning_agent/github_collector.py

Environment variables required:
  ANTHROPIC_API_KEY
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root or from soc_planning_agent/
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import anthropic
from rss_collector import RSSCollector, RSS_SOURCES_DAILY, CATEGORY_KEYWORDS

COLLECTION_MODEL = "claude-haiku-4-5"
DATA_DIR = ROOT / "data"


def summarize_articles(client: anthropic.Anthropic, category: str, articles: list) -> str:
    """Call Claude Haiku to summarize filtered articles for a category."""
    if not articles:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    for i, a in enumerate(articles[:20], 1):
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   Date: {a['published']}\n"
            f"   URL: {a['url']}\n"
            f"   {a['summary'][:400]}"
        )

    prompt = (
        f"Today is {today}. Category: [{category}]\n"
        f"Below are {len(articles)} news articles from the last 24 hours "
        f"(all from credible sources: {', '.join(sorted({a['source'] for a in articles[:5]}))} etc.)\n\n"
        f"Please provide:\n"
        f"1. Top 3-5 most important articles with 2-3 bullet points each\n"
        f"2. For the top 2, apply this framework:\n"
        f"   目標對象 / 創造的價值 / 解決的痛點 / 商業模式 / 產業鏈誘因\n"
        f"3. Keep all URLs\n"
        f"Write in Traditional Chinese, preserve English technical terms.\n\n"
        f"Articles:\n" + "\n\n".join(lines)
    )

    response = client.messages.create(
        model=COLLECTION_MODEL,
        max_tokens=2048,
        system="You are a SoC product planning expert. Summarize tech news concisely.",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== SOC Planning Agent — GitHub Actions Collector ({today}) ===\n")

    # Step 1: Fetch RSS (GitHub Actions has full internet access)
    print("📡 Fetching RSS feeds (last 24h)...")
    collector = RSSCollector(max_age_days=1)
    category_articles = collector.collect_daily()

    total = sum(len(a) for a in category_articles.values())
    print(f"\n✓ Fetched {total} articles across {len(category_articles)} categories\n")

    if total == 0:
        print("⚠ No articles found. Check RSS source availability.")
        # Write empty result so the workflow still has an artifact
        DATA_DIR.mkdir(exist_ok=True)
        out = DATA_DIR / f"{today}.json"
        out.write_text(json.dumps({"date": today, "collections": [], "total_articles": 0}, ensure_ascii=False, indent=2))
        print(f"Wrote empty result to {out}")
        return

    # Step 2: Summarize each category with Claude Haiku
    collections = []
    for category, articles in category_articles.items():
        if not articles:
            continue

        print(f"✍  Summarizing [{category}] ({len(articles)} articles)...")
        summary = summarize_articles(client, category, articles)

        if summary:
            collections.append({
                "category": category,
                "topic": f"Daily RSS digest — {category} ({len(articles)} articles, {today})",
                "content": summary,
                "sources": list(dict.fromkeys(a["url"] for a in articles if a.get("url"))),
                "article_count": len(articles),
            })
            print(f"  ✓ [{category}] summary ready ({len(summary)} chars)")

        # Delay to stay within Haiku rate limits
        time.sleep(5)

    # Step 3: Write JSON output
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"{today}.json"
    result = {
        "date": today,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": total,
        "collections": collections,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Done! {len(collections)} categories → {out_path}")
    print(f"   GitHub Actions will commit this file to the repo.")


if __name__ == "__main__":
    main()
