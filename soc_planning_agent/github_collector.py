"""Standalone collector for GitHub Actions.

Two-pass flow:
  Pass 1 — Classify ALL articles using RSS title + summary only (no HTTP fetch)
            Haiku returns: article_type ('trend'/'info') + one_liner
  Pass 2 — For [trend] articles only: fetch full text → Haiku deep analysis
            [info] articles: keep one_liner, skip full fetch

Output: soc_planning_agent/data/YYYY-MM-DD.json
  Per-article structured data (title, url, type, one_liner, full_text, analysis)

Local agent imports with:  python main.py sync

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

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import anthropic
from rss_collector import RSSCollector

COLLECTION_MODEL = "claude-haiku-4-5"
DATA_DIR = ROOT / "data"
MAX_ARTICLE_CHARS = 2500  # chars sent to Haiku for deep analysis
FETCH_TIMEOUT = 10


# ---------------------------------------------------------------------------
# HTML → plain text
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
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
    return re.sub(r"\s{2,}", " ", " ".join(parser.chunks)).strip()


def fetch_full_text(url: str) -> str:
    """Fetch article and return plain text. Returns '' on failure."""
    if not url or not url.startswith("http"):
        return ""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SoCPlanningAgent/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            if "html" not in resp.headers.get("Content-Type", ""):
                return ""
            return _html_to_text(resp.read(200_000).decode("utf-8", errors="replace"))
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Pass 1 — Classify articles (RSS only, no fetch)
# ---------------------------------------------------------------------------

def classify_articles(client: anthropic.Anthropic, category: str, articles: list) -> list:
    """Ask Haiku to classify each article as 'trend' or 'info' and produce a one_liner.

    Returns articles list with added fields: article_type, one_liner.
    Uses RSS title + summary only — no full text needed.
    """
    if not articles:
        return []

    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a['title']}\n   {a.get('summary','')[:200]}")

    prompt = (
        f"Category: [{category}]. Classify each article as 'trend' or 'info'.\n\n"
        f"Rules:\n"
        f"  trend = new product launch, new technology, new standard, new architecture, "
        f"new market entrant — signals a REAL industry direction change\n"
        f"  info  = personnel change, price change, bug fix, minor feature update, "
        f"earnings report, promotion/deal — operational or informational only\n\n"
        f"Return a JSON array (no markdown, just raw JSON):\n"
        f'[{{"index":1,"type":"trend","one_liner":"..."}},{{"index":2,"type":"info","one_liner":"..."}},...]\n\n'
        f"one_liner: one concise sentence in Traditional Chinese explaining why it matters (or doesn't).\n\n"
        f"Articles:\n" + "\n\n".join(lines)
    )

    try:
        resp = client.messages.create(
            model=COLLECTION_MODEL,
            max_tokens=1500,
            system="You are a SoC product planning expert. Return only valid JSON, no explanation.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        classifications = json.loads(raw)
        lookup = {item["index"]: item for item in classifications}
    except Exception as e:
        print(f"    ⚠ Classification parse error: {e} — defaulting all to 'info'")
        lookup = {}

    enriched = []
    for i, a in enumerate(articles, 1):
        c = lookup.get(i, {})
        enriched.append({
            **a,
            "article_type": c.get("type", "info"),
            "one_liner": c.get("one_liner", ""),
        })
    return enriched


# ---------------------------------------------------------------------------
# Pass 2 — Deep analysis for trend articles only
# ---------------------------------------------------------------------------

def analyze_trend_article(client: anthropic.Anthropic, article: dict) -> dict:
    """Fetch full text and apply 5-dimension deep analysis framework."""
    url = article.get("url", "")
    print(f"    📄 Fetching full text: {url[:80]}")
    full_text = fetch_full_text(url)

    # Fallback to RSS summary if fetch yields too little
    rss_summary = article.get("summary", "")
    if len(full_text) < len(rss_summary) + 200:
        full_text = rss_summary
        fetch_ok = False
    else:
        fetch_ok = True

    body = full_text[:MAX_ARTICLE_CHARS]

    prompt = (
        f"Article: {article['title']}\n"
        f"Source: {article.get('source','')} | Published: {article.get('published','')}\n"
        f"URL: {url}\n\n"
        f"Content:\n{body}\n\n"
        f"Apply the SoC product planning deep analysis framework in Traditional Chinese "
        f"(keep English technical terms). Use this exact structure:\n\n"
        f"## 目標對象\n（服務誰？消費者/企業/開發者/電信業者/基礎設施廠商）\n\n"
        f"## 創造的價值\n（具體好處、量化指標優先）\n\n"
        f"## 解決的痛點\n（解決了什麼現有問題？現有方案的不足）\n\n"
        f"## 商業模式\n（誰付錢？一次性/訂閱/晶片銷售/IP授權）\n\n"
        f"## 產業鏈誘因\n（IP→晶片→foundry→OEM→電信業者→消費者，每層動機與障礙）"
    )

    try:
        resp = client.messages.create(
            model=COLLECTION_MODEL,
            max_tokens=1500,
            system="You are a SoC product planning expert. Be concise and evidence-based.",
            messages=[{"role": "user", "content": prompt}],
        )
        analysis = resp.content[0].text.strip()
    except Exception as e:
        analysis = f"（分析失敗：{e}）"

    return {
        **article,
        "full_text": body,
        "fetch_ok": fetch_ok,
        "analysis": analysis,
    }


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

    # Step 1: Fetch RSS
    print("📡 Fetching RSS feeds (last 24h)...")
    collector = RSSCollector(max_age_days=1)
    category_articles = collector.collect_daily()
    total = sum(len(a) for a in category_articles.values())
    print(f"✓ {total} articles across {len(category_articles)} categories\n")

    if total == 0:
        print("⚠ No articles found.")
        DATA_DIR.mkdir(exist_ok=True)
        out = DATA_DIR / f"{today}.json"
        out.write_text(json.dumps(
            {"date": today, "collections": [], "total_articles": 0},
            ensure_ascii=False, indent=2,
        ))
        return

    # Step 2 (Pass 1): Classify all articles using RSS title + summary only
    print("🏷  Pass 1 — Classifying articles (RSS only, no fetch)...")
    classified_by_category = {}
    for category, articles in category_articles.items():
        if not articles:
            continue
        print(f"  [{category}] {len(articles)} articles")
        classified = classify_articles(client, category, articles)
        n_trend = sum(1 for a in classified if a["article_type"] == "trend")
        n_info  = sum(1 for a in classified if a["article_type"] == "info")
        print(f"    → {n_trend} [趨勢類]  {n_info} [資訊類]")
        classified_by_category[category] = classified
        time.sleep(3)

    # Step 3 (Pass 2): Fetch full text + deep analysis for trend articles only
    print("\n🔬 Pass 2 — Deep analysis for [趨勢類] articles...")
    final_by_category = {}
    for category, articles in classified_by_category.items():
        final = []
        for a in articles:
            if a["article_type"] == "trend":
                a = analyze_trend_article(client, a)
                time.sleep(2)
            else:
                # Info articles: keep RSS summary, no full text needed
                a = {**a, "full_text": "", "analysis": ""}
            final.append(a)
        final_by_category[category] = final

    # Step 4: Build output JSON
    collections = []
    for category, articles in final_by_category.items():
        n_trend = sum(1 for a in articles if a["article_type"] == "trend")
        collections.append({
            "category": category,
            "topic": f"Daily RSS digest — {category} ({len(articles)} articles, {today})",
            "article_count": len(articles),
            "trend_count": n_trend,
            "articles": [
                {
                    "title":        a["title"],
                    "url":          a.get("url", ""),
                    "source":       a.get("source", ""),
                    "published":    a.get("published", ""),
                    "article_type": a["article_type"],
                    "one_liner":    a.get("one_liner", ""),
                    "rss_summary":  a.get("summary", ""),
                    "full_text":    a.get("full_text", ""),
                    "analysis":     a.get("analysis", ""),
                }
                for a in articles
            ],
        })
        print(f"  ✓ [{category}] {len(articles)} articles ({n_trend} trend)")

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"{today}.json"
    result = {
        "date": today,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": total,
        "collections": collections,
        "format_version": 2,  # structured per-article format
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Done! {len(collections)} categories → {out_path}")


if __name__ == "__main__":
    main()
