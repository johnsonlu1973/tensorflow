"""Standalone collector for GitHub Actions.

Runs in GitHub Actions (full internet access, no proxy restrictions).
Fetches RSS → fetches full article text → classifies → summarizes with Claude Haiku → writes JSON.

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
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

# Allow running from repo root or from soc_planning_agent/
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import anthropic
from rss_collector import RSSCollector

COLLECTION_MODEL = "claude-haiku-4-5"
DATA_DIR = ROOT / "data"

# Max chars of article body to send to Haiku (keep token cost low)
MAX_ARTICLE_CHARS = 2000
FETCH_TIMEOUT = 10  # seconds per URL


# ---------------------------------------------------------------------------
# HTML → plain text (stdlib only, no BeautifulSoup)
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Strip HTML tags and extract visible text."""

    SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header",
                 "aside", "form", "button", "svg", "meta", "link"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            text = data.strip()
            if text:
                self.chunks.append(text)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    raw = " ".join(parser.chunks)
    # Collapse whitespace
    return re.sub(r"\s{2,}", " ", raw).strip()


# ---------------------------------------------------------------------------
# Full article fetcher
# ---------------------------------------------------------------------------

def fetch_full_text(url: str) -> str:
    """Fetch article URL and return plain text body.

    Returns empty string on any error (paywall, JS-heavy, timeout, etc.).
    Falls back gracefully — caller uses RSS summary if this returns "".
    """
    if not url or not url.startswith("http"):
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; SoCPlanningAgent/1.0; "
                    "+https://github.com/johnsonlu1973/tensorflow)"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type:
                return ""
            raw_html = resp.read(200_000).decode("utf-8", errors="replace")
        return _html_to_text(raw_html)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Per-article enrichment
# ---------------------------------------------------------------------------

def enrich_articles(articles: list) -> list:
    """Add 'full_text' field to each article by fetching the URL.

    Falls back to RSS 'summary' field if fetch fails or returns too little text.
    """
    enriched = []
    for i, article in enumerate(articles, 1):
        url = article.get("url", "")
        print(f"    [{i}/{len(articles)}] Fetching: {url[:80]}")
        full = fetch_full_text(url)

        # Use full text only if it's meaningfully longer than the RSS snippet
        rss_summary = article.get("summary", "")
        if len(full) > len(rss_summary) + 200:
            article = dict(article)  # shallow copy
            article["full_text"] = full[:MAX_ARTICLE_CHARS]
            article["fetch_status"] = "ok"
        else:
            article = dict(article)
            article["full_text"] = rss_summary  # RSS fallback
            article["fetch_status"] = "fallback"

        enriched.append(article)
        time.sleep(0.5)  # polite crawl delay

    ok = sum(1 for a in enriched if a["fetch_status"] == "ok")
    print(f"    → {ok}/{len(enriched)} full texts fetched, {len(enriched)-ok} used RSS fallback")
    return enriched


# ---------------------------------------------------------------------------
# Haiku summarization with classification
# ---------------------------------------------------------------------------

def summarize_articles(client: anthropic.Anthropic, category: str, articles: list) -> str:
    """Call Claude Haiku to classify and summarize articles.

    Classification rules (applied by Haiku):
    [趨勢類] new product / new technology / new standard / new architecture / new market entrant
    [資訊類] personnel change / price change / bug fix / minor feature update / earnings / promotions

    Deep framework (目標對象 / 創造的價值 / 解決的痛點 / 商業模式 / 產業鏈誘因)
    is applied ONLY to [趨勢類] articles.
    """
    if not articles:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    for i, a in enumerate(articles[:20], 1):
        body = a.get("full_text") or a.get("summary", "")
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   Date: {a.get('published','')}\n"
            f"   URL: {a['url']}\n"
            f"   Content: {body[:MAX_ARTICLE_CHARS]}"
        )

    sources_str = ", ".join(sorted({a["source"] for a in articles[:5]}))
    prompt = (
        f"Today is {today}. Category: [{category}]\n"
        f"Below are {len(articles)} articles from credible sources ({sources_str} etc.).\n\n"
        f"**STEP 1 — Classify each article into ONE of two types:**\n"
        f"  [趨勢類] new product launch, new technology, new standard, new architecture, "
        f"new market entrant — signals a REAL industry shift\n"
        f"  [資訊類] personnel change, price change, bug fix / recall, minor feature update, "
        f"earnings report, promotions / deals — informational only\n\n"
        f"**STEP 2 — Output format (Traditional Chinese, keep English technical terms):**\n"
        f"A. List ALL [趨勢類] articles:\n"
        f"   - Title + URL + 2-3 bullet points\n"
        f"   - For the TOP 1-2 most significant [趨勢類] articles, add a deep analysis table:\n"
        f"     | 維度 | 內容 |\n"
        f"     目標對象 / 創造的價值 / 解決的痛點 / 商業模式 / 產業鏈誘因\n"
        f"     (IP→晶片→foundry→OEM→電信業者→消費者)\n\n"
        f"B. List ALL [資訊類] articles:\n"
        f"   - Title + one-sentence summary only. NO framework analysis.\n\n"
        f"Articles:\n" + "\n\n".join(lines)
    )

    response = client.messages.create(
        model=COLLECTION_MODEL,
        max_tokens=3000,
        system=(
            "You are a SoC product planning expert. "
            "Your goal is to identify REAL technology trends from daily news. "
            "Be precise: only apply the deep framework to news that genuinely signals "
            "an industry direction change, not to operational or promotional news."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
        DATA_DIR.mkdir(exist_ok=True)
        out = DATA_DIR / f"{today}.json"
        out.write_text(json.dumps(
            {"date": today, "collections": [], "total_articles": 0},
            ensure_ascii=False, indent=2,
        ))
        print(f"Wrote empty result to {out}")
        return

    # Step 2: Fetch full article text for each category
    print("📄 Fetching full article texts...\n")
    enriched_by_category = {}
    for category, articles in category_articles.items():
        if not articles:
            continue
        print(f"  [{category}] — {len(articles)} articles")
        enriched_by_category[category] = enrich_articles(articles)

    # Step 3: Classify + summarize each category with Claude Haiku
    print("\n✍  Summarizing with Claude Haiku (classify → framework)...\n")
    collections = []
    for category, articles in enriched_by_category.items():
        print(f"  Summarizing [{category}] ({len(articles)} articles)...")
        summary = summarize_articles(client, category, articles)

        if summary:
            collections.append({
                "category": category,
                "topic": f"Daily RSS digest — {category} ({len(articles)} articles, {today})",
                "content": summary,
                "sources": list(dict.fromkeys(a["url"] for a in articles if a.get("url"))),
                "article_count": len(articles),
            })
            print(f"  ✓ [{category}] done ({len(summary)} chars)")

        time.sleep(5)  # Haiku rate-limit buffer

    # Step 4: Write JSON output
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
    print("   GitHub Actions will commit this file to the repo.")


if __name__ == "__main__":
    main()
