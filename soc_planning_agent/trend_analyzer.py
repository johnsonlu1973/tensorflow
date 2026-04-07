"""Weekly trend analyzer — structural opportunity detection, 矛盾點 warnings, Red Teaming.

Flow:
  1. Load past N days of archived RSS (archive/rss/*.json)
  2. Cluster articles by category/keyword
  3. Ask Claude Opus to:
     - Identify structural opportunities (4-layer framework)
     - Detect contradictions (矛盾點) between overseas vs Taiwan reports
     - Generate Red Teaming adversarial challenges for each opportunity
  4. Write trend HTML to docs/trend_{date}.html
  5. Update index.html with trend link
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT     = Path(__file__).parent
ARCHIVE_RSS_DIR = ROOT / "archive" / "rss"
DOCS_DIR = ROOT.parent / "docs"

MODEL_TREND = "claude-opus-4-6"
GITHUB_REPO = "johnsonlu1973/tensorflow"
PAGES_URL   = "https://johnsonlu1973.github.io/tensorflow"

CATEGORY_LABEL = {
    "chips_soc":   ("💾", "Chips / SoC"),
    "mobile":      ("📱", "Mobile"),
    "agentic_ai":  ("🤖", "Agentic AI"),
    "5g_cpe":      ("📡", "5G / CPE"),
    "csp_cloud":   ("☁️", "CSP / Cloud"),
    "tech_general":("🌐", "Tech General"),
    "taiwan":      ("🇹🇼", "台灣"),
}

OVERSEAS_CATS = {"chips_soc", "mobile", "agentic_ai", "5g_cpe", "csp_cloud", "tech_general"}
TAIWAN_CATS   = {"taiwan"}


# ---------------------------------------------------------------------------
# Load archive data
# ---------------------------------------------------------------------------

def load_recent_articles(days: int = 7) -> list[dict]:
    """Load articles from the past N days of RSS archives."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []
    if not ARCHIVE_RSS_DIR.exists():
        return articles

    for f in sorted(ARCHIVE_RSS_DIR.glob("*.json")):
        try:
            date_str = f.stem  # YYYY-MM-DD
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            for a in data.get("articles", []):
                a["_archive_date"] = date_str
                articles.append(a)
        except Exception as e:
            print(f"  ⚠ skip {f.name}: {e}")

    print(f"📂 Loaded {len(articles)} articles from past {days} days")
    return articles


# ---------------------------------------------------------------------------
# Build summary for Claude analysis
# ---------------------------------------------------------------------------

def _build_category_summary(articles: list[dict]) -> dict[str, list]:
    """Group articles by category, return top N per category for Claude input."""
    by_cat: dict[str, list] = {}
    for a in articles:
        cat = a.get("category", "unknown")
        by_cat.setdefault(cat, []).append(a)
    return by_cat


def _format_articles_for_prompt(articles: list[dict], max_per_cat: int = 15) -> str:
    """Render articles as compact text for Claude analysis."""
    by_cat = _build_category_summary(articles)
    lines = []
    for cat, arts in by_cat.items():
        emoji, label = CATEGORY_LABEL.get(cat, ("📰", cat))
        lines.append(f"\n## {emoji} {label} ({len(arts)} 篇)")
        for a in arts[:max_per_cat]:
            title = a.get("title_zh") or a.get("title", "")
            summary = (a.get("summary_zh") or a.get("summary", ""))[:200]
            src = a.get("source", "")
            pub = (a.get("published", "") or a.get("_archive_date", ""))[:10]
            lines.append(f"- [{src} {pub}] {title}")
            if summary:
                lines.append(f"  ↳ {summary}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude Opus trend analysis
# ---------------------------------------------------------------------------

TREND_SYSTEM = """你是 SoC 產品規劃策略師，專長於晶片市場情報分析和競爭策略。
你的分析需要：繁體中文為主、英文技術術語保留原文、輸出結構清晰。"""

TREND_PROMPT = """請分析以下過去一週的市場情報摘要，完成三項分析任務。

{article_summary}

---

## 任務一：結構性機會偵測（Structural Opportunity Detection）

找出 2-3 個最重要的結構性機會：
- 哪些產業力量的交叉點正在形成新市場？
- 引用具體文章作為依據（格式：[來源 日期]）
- 每個機會套用 4 層框架：
  🔵 啟動層：觸發趨勢
  🟡 鎖定層：目標客群與痛點
  🟢 轉換層：解決方案與差異化
  🔴 收成層：商業價值與護城河

---

## 任務二：矛盾點警告（Contradiction Warnings）

比對海外媒體 vs 台灣媒體的報導落差：
- 是否有「海外說需求放緩，台灣供應鏈卻在增產」的矛盾？
- 是否有技術路線的分歧（例如：海外推 Wi-Fi 7，台灣廠商仍聚焦 5G CPE）？
- 每個矛盾點說明：可能原因、對 SoC 規劃的影響、建議監測指標

---

## 任務三：Red Teaming（對抗性提問）

針對任務一找到的機會，扮演「反方競爭對手」提出 3-5 個最刁鑽的挑戰：
- 這個機會是否已經被 Qualcomm/MediaTek 先佔了？
- 客戶為什麼不能用現有方案解決？
- 技術門檻是否比想像中高？
- 市場時機是否太早或太晚？
- 供應鏈依賴風險？

每個挑戰後提供「應對策略」。

---

## 任務四：本週關鍵數字

列出本週文章中出現的具體數字、市場預測、規格指標（不要捏造，只引用原文）。

---

請用繁體中文輸出，保留英文技術術語。每個任務分開輸出，格式清晰。"""


def run_trend_analysis(client, articles: list[dict]) -> str:
    """Call Claude Opus to run full trend analysis. Returns markdown text."""
    article_summary = _format_articles_for_prompt(articles, max_per_cat=15)
    prompt = TREND_PROMPT.format(article_summary=article_summary)

    print(f"  → Sending {len(articles)} articles to Claude {MODEL_TREND}...")
    try:
        resp = client.messages.create(
            model=MODEL_TREND,
            max_tokens=8000,
            system=TREND_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        return f"⚠️ Analysis failed: {e}"


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

_CSS_TREND = """
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #c9d1d9; --text-dim: #8b949e; --text-bright: #e6edf3;
  --blue: #58a6ff; --green: #3fb950; --yellow: #e3b341;
  --red: #f85149; --purple: #bc8cff;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  padding: 16px 12px; max-width: 860px; margin: 0 auto; line-height: 1.7;
}
a { color: var(--blue); }
h1 { color: var(--blue); font-size: 1.3em; margin-bottom: 4px; }
h2 { color: var(--yellow); font-size: 1.05em; margin: 24px 0 10px;
     border-bottom: 1px solid var(--border); padding-bottom: 6px; }
h3 { color: var(--green); font-size: 0.95em; margin: 16px 0 6px; }
.page-meta { color: var(--text-dim); font-size: 0.8em; margin-bottom: 20px; }
.back { color: var(--blue); text-decoration: none; font-size: 0.82em;
        display: inline-block; margin-bottom: 14px; }
.back:hover { text-decoration: underline; }
.stat-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.stat-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 16px; flex: 1; min-width: 120px;
}
.stat-box .label { font-size: 0.72em; color: var(--text-dim); }
.stat-box .value { font-size: 1.4em; font-weight: 700; color: var(--text-bright); }
.analysis-body {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px 20px; line-height: 1.8;
  white-space: pre-wrap; font-size: 0.88em;
}
.contradiction { border-left: 3px solid var(--red); padding-left: 12px; margin: 12px 0; }
.opportunity   { border-left: 3px solid var(--green); padding-left: 12px; margin: 12px 0; }
.redteam       { border-left: 3px solid var(--yellow); padding-left: 12px; margin: 12px 0; }
.cat-breakdown {
  display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0;
}
.cat-pill {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 3px 10px; font-size: 0.75em;
  color: var(--text-dim);
}
"""

def _render_trend_html(date: str, analysis_text: str, articles: list[dict],
                        period_days: int) -> str:
    by_cat = _build_category_summary(articles)
    total  = len(articles)

    cat_pills = ""
    for cat, arts in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        emoji, label = CATEGORY_LABEL.get(cat, ("📰", cat))
        cat_pills += f'<span class="cat-pill">{emoji} {label} {len(arts)}</span>'

    # Escape the analysis text for HTML pre-wrap display
    def _esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📈 週趨勢分析 — {date}</title>
<style>{_CSS_TREND}</style>
</head>
<body>
<a class="back" href="index.html">← 返回總覽</a>
<h1>📈 SOC 市場週趨勢分析</h1>
<div class="page-meta">分析日期：{date} &nbsp;·&nbsp; 涵蓋過去 {period_days} 天</div>

<div class="stat-row">
  <div class="stat-box">
    <div class="label">分析文章</div>
    <div class="value">{total}</div>
  </div>
  <div class="stat-box">
    <div class="label">涵蓋類別</div>
    <div class="value">{len(by_cat)}</div>
  </div>
  <div class="stat-box">
    <div class="label">分析模型</div>
    <div class="value" style="font-size:0.85em">Claude Opus</div>
  </div>
</div>

<div class="cat-breakdown">{cat_pills}</div>

<h2>🔍 Claude Opus 深度分析</h2>
<div class="analysis-body">{_esc(analysis_text)}</div>

</body></html>"""


# ---------------------------------------------------------------------------
# Index update
# ---------------------------------------------------------------------------

def _update_index_with_trend(trend_filename: str, date: str, total_articles: int):
    """Prepend trend report link to index.html."""
    index_path = DOCS_DIR / "index.html"
    if not index_path.exists():
        return

    existing = index_path.read_text(encoding="utf-8")
    trend_card = f"""
<a class="index-card" href="{trend_filename}" style="border-color:#e3b341">
  <h2>📈 週趨勢分析 — {date}</h2>
  <div class="card-meta">分析 {total_articles} 篇文章 &nbsp;·&nbsp; <span class="new-count">Claude Opus</span></div>
</a>"""

    # Insert after <br> or just before existing cards
    updated = existing.replace("<br>\n", f"<br>\n{trend_card}\n", 1)
    if updated == existing:
        # Fallback: insert before first index-card
        updated = existing.replace('<a class="index-card"', trend_card + '\n<a class="index-card"', 1)

    index_path.write_text(updated, encoding="utf-8")
    print(f"  ✓ index.html updated with trend link")


# ---------------------------------------------------------------------------
# Slack notification
# ---------------------------------------------------------------------------

def send_slack_trend(webhook_url: str, date: str, total_articles: int,
                     analysis_text: str):
    """Send Slack notification for weekly trend report."""
    import urllib.request
    import urllib.parse

    # Extract first structural opportunity (first 300 chars of analysis)
    preview = analysis_text[:400].replace("\n", " ").replace('"', '\\"')

    payload = json.dumps({
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📈 SOC 週趨勢分析報告", "emoji": True}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*📅 分析日期*\n{date}"},
                    {"type": "mrkdwn", "text": f"*📰 分析文章*\n{total_articles} 篇（過去 7 天）"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*分析摘要*\n{preview[:280]}..."}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📊 查看完整趨勢報告"},
                        "url": PAGES_URL
                    }
                ]
            }
        ]
    })

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"  ✓ Slack trend notification sent (HTTP {r.status})")
    except Exception as e:
        print(f"  ⚠ Slack notification failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    period_days = int(os.environ.get("TREND_DAYS", "7"))
    client = anthropic.Anthropic(api_key=api_key)
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== SOC Planning — Weekly Trend Analyzer ({today}, {period_days}d) ===\n")

    # Load recent articles
    articles = load_recent_articles(days=period_days)
    if len(articles) < 5:
        print(f"⚠ Only {len(articles)} articles found — skipping analysis")
        _write_output(0, today)
        return

    # Run analysis
    print(f"\n🧠 Running Claude {MODEL_TREND} trend analysis...")
    analysis = run_trend_analysis(client, articles)
    print(f"  ✓ Analysis complete ({len(analysis)} chars)")

    # Generate HTML
    DOCS_DIR.mkdir(exist_ok=True)
    trend_fname = f"trend_{today}.html"
    html = _render_trend_html(today, analysis, articles, period_days)
    (DOCS_DIR / trend_fname).write_text(html, encoding="utf-8")
    print(f"\n📄 Saved: docs/{trend_fname}")

    # Update index
    _update_index_with_trend(trend_fname, today, len(articles))

    # Slack notification
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if webhook:
        send_slack_trend(webhook, today, len(articles), analysis)

    _write_output(len(articles), today)
    print(f"\n✅ Trend analysis done — {len(articles)} articles analyzed")


def _write_output(article_count: int, today: str):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"trend_articles={article_count}\n")
            f.write(f"today={today}\n")
            f.write(f"pages_url={PAGES_URL}\n")


if __name__ == "__main__":
    main()
