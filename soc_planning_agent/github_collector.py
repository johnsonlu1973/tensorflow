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
import socket
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
    """Fetch article and return plain text. Returns '' on failure.

    Uses socket-level default timeout as a hard backstop — urllib's timeout
    parameter only covers the initial connection, not the full read.
    """
    if not url or not url.startswith("http"):
        return ""
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(FETCH_TIMEOUT)
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
    finally:
        socket.setdefaulttimeout(old_timeout)


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
        f"STRICT definition of 'trend' — must meet ALL of these:\n"
        f"  ✅ INNOVATIVE, LEADING, or BREAKTHROUGH — not just an incremental improvement\n"
        f"  ✅ Creates a NEW market opportunity or breaks an existing market equilibrium\n"
        f"  ✅ Enables a new category of use cases that was previously impossible or impractical\n"
        f"  Examples of TREND: first on-device LLM SoC, new 3GPP standard enabling new service, "
        f"new AI-native OS paradigm, first-of-its-kind product category\n\n"
        f"  ❌ NOT trend (even if labelled 'new'): iterative spec upgrades (faster chip/more RAM), "
        f"feature additions to existing products, new model in existing product line, "
        f"software patches, personnel changes, pricing, promotions, earnings\n\n"
        f"Return a JSON array (no markdown, just raw JSON):\n"
        f'[{{"index":1,"type":"trend","one_liner":"..."}},{{"index":2,"type":"info","one_liner":"..."}},...]\n\n'
        f"one_liner: one concise sentence in Traditional Chinese. "
        f"For trend: explain what NEW opportunity/paradigm this signals. "
        f"For info: explain what happened in one line.\n\n"
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
        f"This article represents a BREAKTHROUGH or INNOVATIVE development. "
        f"Apply the 4-layer strategic analysis framework in Traditional Chinese "
        f"(keep English technical terms). Follow EXACTLY this structure:\n\n"
        f"⚠️ EMPTY FIELD RULE: If the article does not contain enough information "
        f"to answer a specific field, write EXACTLY '（原文未提及）' for that field. "
        f"Never fabricate, infer, or hallucinate content to fill gaps. "
        f"It is perfectly acceptable to have empty fields.\n\n"

        f"## 啟動層：趨勢 → 市場新機會\n"
        f"**產業趨勢**：哪些技術突破或典範轉移正在發生？（從原文找依據）\n"
        f"**市場新機會**：這個趨勢打破了哪個現有市場平衡？創造了什麼尚未被滿足的新機會？\n\n"

        f"## 鎖定層：機會 → 目標客群與痛點\n"
        f"**目標客群**：在這個新機會中，誰是最核心的目標客群？（直接客戶 vs 終端用戶）\n"
        f"**最急迫的痛點**：他們目前最急迫的問題是什麼？\n"
        f"**現有方案的不足**：為什麼現有解決方案無法解決？差距在哪裡？\n\n"

        f"## 轉換層：痛點 → 客戶價值\n"
        f"**解決方案**：這個新產品/技術具體如何解決痛點？\n"
        f"**差異化優勢**：比競爭對手更好／更快／更便宜在哪裡？\n"
        f"**客戶價值**：為客戶創造了什麼具體可感受的價值？\n"
        f"⚠️ 數字規則：只引用原文明確出現的數字。原文無數字則定性描述。"
        f"推估須標示「（推估）」並說明依據，禁止捏造數據。\n\n"

        f"## 收成層：客戶價值 → 商業價值\n"
        f"**商業模式**：如何將客戶價值轉換成公司收入？（硬體溢價／軟體訂閱／IP授權／平台費）\n"
        f"**護城河**：什麼機制讓競爭對手難以複製？（生態綁定／技術壁壘／轉換成本／網絡效應）\n"
        f"**商業價值**：對公司財務的預期影響（ASP提升／市佔擴大／毛利改善）\n"
        f"⚠️ 同樣規則：財務數字只引原文，無原文數字則定性描述或標示「（推估）」\n\n"

        f"## 產業鏈結構圖\n"
        f"用 ASCII 畫出這個新機會涉及的產業結構，從消費端往上游延伸，標出旁支 ecosystem：\n"
        f"```\n"
        f"（依實際產業繪製，例如：）\n"
        f"消費者／企業\n"
        f"  ↓\n"
        f"OEM／平台商\n"
        f"  ↓           ↓\n"
        f"晶片設計      CSP/Cloud\n"
        f"  ↓\n"
        f"Foundry\n"
        f"  ↓\n"
        f"IP廠商\n"
        f"```\n\n"

        f"## 產業鏈誘因分析\n"
        f"從目標客群的商業價值出發，逐層分析各產業參與者的誘因。用表格呈現：\n"
        f"| 產業層級 | 誘因來源（承接下游商業價值） | 誘因強度 | 潛在障礙／利益衝突 | 態度 |\n"
        f"|---------|--------------------------|--------|-----------------|------|\n"
        f"誘因強度：🔴高 🟡中 🟢低\n"
        f"態度：積極主導 / 積極支持 / 觀望 / 被動跟進 / 抵制\n\n"
        f"最後補充：\n"
        f"- 這個突破是否破壞現有產業鏈結構？誰受益誰受損？\n"
        f"- 既有廠商（incumbents）的態度與可能的應對策略？\n"
        f"- 新進入者的能力條件與機會窗口？\n"
    )

    try:
        resp = client.messages.create(
            model=COLLECTION_MODEL,
            max_tokens=1500,
            system=(
                "You are a SoC product planning expert. Be concise and evidence-based. "
                "CRITICAL RULE: Never fabricate numbers, statistics, or percentages. "
                "Only cite figures that appear verbatim in the provided article text. "
                "If no data exists in the article, use qualitative descriptions only. "
                "If you must estimate, clearly label it as （推估） and explain the basis."
            ),
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
    # Cap at MAX_TREND_PER_CATEGORY per category to keep runtime predictable
    MAX_TREND_PER_CATEGORY = 3
    print(f"\n🔬 Pass 2 — Deep analysis for [趨勢類] articles (max {MAX_TREND_PER_CATEGORY}/category)...")
    final_by_category = {}
    for category, articles in classified_by_category.items():
        final = []
        trend_count = 0
        for a in articles:
            if a["article_type"] == "trend" and trend_count < MAX_TREND_PER_CATEGORY:
                a = analyze_trend_article(client, a)
                trend_count += 1
                time.sleep(2)
            elif a["article_type"] == "trend":
                # Over cap: downgrade to info display (keep one_liner, skip fetch)
                a = {**a, "full_text": "", "analysis": "", "article_type": "trend_summary"}
            else:
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
