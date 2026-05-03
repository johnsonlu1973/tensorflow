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

MODEL_TREND = "claude-opus-4-7"
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
    """Load articles from past N days of RSS archives + user bookmarks/fulltext."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []

    # ── RSS archive ──
    if ARCHIVE_RSS_DIR.exists():
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

    # ── User bookmarks (⭐ marked as interesting) ──
    bookmark_dir = ROOT / "archive" / "bookmarks"
    if bookmark_dir.exists():
        seen_urls = {a.get("url") for a in articles}
        for f in sorted(bookmark_dir.glob("*.json"), reverse=True)[:50]:
            try:
                a = json.loads(f.read_text(encoding="utf-8"))
                if a.get("url") not in seen_urls:
                    a["_user_bookmarked"] = True
                    a["category"] = a.get("category", "bookmarked")
                    articles.append(a)
                    seen_urls.add(a.get("url"))
                else:
                    # Mark existing article as bookmarked
                    for existing in articles:
                        if existing.get("url") == a.get("url"):
                            existing["_user_bookmarked"] = True
                            break
            except Exception as e:
                print(f"  ⚠ skip bookmark {f.name}: {e}")

    # ── User fulltext saves (pasted full text = high interest) ──
    fulltext_dir = ROOT / "archive" / "fulltext"
    if fulltext_dir.exists():
        for f in sorted(fulltext_dir.glob("*.json"), reverse=True)[:50]:
            try:
                a = json.loads(f.read_text(encoding="utf-8"))
                for existing in articles:
                    if existing.get("url") == a.get("url"):
                        existing["_user_fulltext"] = True
                        existing["_fulltext_content"] = a.get("fulltext", "")[:500]
                        break
            except Exception:
                pass

    bookmarked = sum(1 for a in articles if a.get("_user_bookmarked"))
    print(f"📂 Loaded {len(articles)} articles from past {days} days ({bookmarked} bookmarked by user)")
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
    # User-bookmarked articles go first, clearly marked
    bookmarked = [a for a in articles if a.get("_user_bookmarked") or a.get("_user_fulltext")]
    if bookmarked:
        lines = ["\n## ⭐ 使用者標記重要（優先分析）"]
        for a in bookmarked:
            title = a.get("title_zh") or a.get("title", "")
            src   = a.get("source", "")
            pub   = (a.get("published", "") or a.get("_archive_date", ""))[:10]
            flag  = "【全文已讀】" if a.get("_user_fulltext") else "【已加關注】"
            lines.append(f"- {flag} [{src} {pub}] {title}")
    else:
        lines = []

    by_cat = _build_category_summary(articles)
    for cat, arts in by_cat.items():
        emoji, label = CATEGORY_LABEL.get(cat, ("📰", cat))
        lines.append(f"\n## {emoji} {label} ({len(arts)} 篇)")
        for a in arts[:max_per_cat]:
            title = a.get("title_zh") or a.get("title", "")
            summary = (a.get("summary_zh") or a.get("summary", ""))[:200]
            src = a.get("source", "")
            pub = (a.get("published", "") or a.get("_archive_date", ""))[:10]
            star = "⭐ " if (a.get("_user_bookmarked") or a.get("_user_fulltext")) else ""
            lines.append(f"- {star}[{src} {pub}] {title}")
            if summary:
                lines.append(f"  ↳ {summary}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude Opus trend analysis
# ---------------------------------------------------------------------------

TREND_SYSTEM = """# SOC 策略分析 System Prompt
# 版本：v3.0｜2026-04-20

你是 SoC 產品規劃策略師，專長於晶片市場情報分析和競爭策略。
輸出語言：繁體中文為主，英文技術術語保留原文，結構清晰。

---

## 規則一：標記每個主張的來源類型

輸出任何主張前，必須選擇以下其中一個標記：
- [來源] — 有明確外部文件或網頁可驗證
- [推斷] — 從有來源的事實邏輯推導，但本身沒有來源
- [未驗證] — 沒有來源，也沒有完整推論鏈

沒有標記 = 違規。[推斷] 和 [未驗證] 不能寫成陳述句。

---

## 規則二：因果鏈每個箭頭都要說明機制

寫出 A → B 之前，必須先說明「A 造成 B 的機制是什麼」。
如果說不出機制，就把 A → B 改寫成：
「A 和 B 都存在，但 A 是否造成 B 需要驗證。[未驗證]」

---

## 規則三：修正時明確列出不受影響的分析

修正一個錯誤結論時，輸出格式必須包含：
修正：[原主張]
原因：[哪裡出錯]
不受影響：[哪些分析和本次修正無關，仍然有效]
「不受影響」這一行不能省略。

---

## 規則四：時效性敏感的主張標記資料時間

市場數據、標準進度、產品規格、競品動態等可能過期的主張，
必須標記資料時間：[來源：XXX，2025.03]
時間不明時標：[時間不明，建議搜尋確認]"""


TREND_PROMPT = """請分析以下過去一週的市場情報摘要，完成三項分析任務。
套用 System Prompt 四條規則：每個主張標記 [來源]/[推斷]/[未驗證]，每個因果箭頭說明機制。

{article_summary}

---

## 任務一：結構性機會偵測（Structural Opportunity Detection）

找出 2-3 個最重要的結構性機會，每個機會必須完整回答以下因果鏈：

**🔵 啟動層：新趨勢 → 新機會**
- 這個趨勢是什麼？（引用具體文章 [來源 日期]）
- **機制說明**：這個趨勢為什麼會打破現有市場均衡？它改變了哪個供需關係、技術可行性、或法規條件？
  → 如果說不清楚機制，標記 [未驗證] 並說明缺什麼資訊。

**🟡 鎖定層：新機會 → 目標客群與痛點**
- 這個機會讓哪個客群現在可以完成過去做不到的 task？
- **機制說明**：為什麼是「現在」才能完成？過去的技術/成本/生態缺了什麼，讓這個 task 無法完成？
- 這個客群最急迫的痛點是什麼？現有方案為何無法解決（具體說明不足之處）？
  → 不能只說「需求增加」，必須說出阻止客群完成 task 的具體機制。

**🟢 轉換層：解決方案 → 客戶價值**
- 這個解決方案如何解決上述痛點？（說明技術或商業機制）
- **機制說明**：為什麼這個方案帶來的價值是現有廠商（Qualcomm/MediaTek/Intel）做不到的？
  是技術壁壘、時間窗口、生態位置、還是成本結構？
  → 如果現有廠商能輕易複製，標記 [未驗證] 並說明差異化假設。

**🔴 收成層：客戶價值 → 商業價值**
- **機制說明**：為什麼這個商業模式可以把客戶價值轉化成可持續的商業利益？
  定價權來自哪裡？客戶為何不會轉向競品？護城河是什麼，它會隨時間加深還是消失？
- 預估市場規模與時間窗口（標記資料時間）。

---

## 任務二：矛盾點警告（Contradiction Warnings）

比對海外媒體 vs 台灣媒體的報導落差：
- 是否有「海外說需求放緩，台灣供應鏈卻在增產」的矛盾？
- 是否有技術路線的分歧？
- 每個矛盾點說明：可能原因（標記 [推斷] 或 [未驗證]）、對 SoC 規劃的影響、建議監測指標。

---

## 任務三：Red Teaming（對抗性提問）

針對任務一的每個機會，扮演「反方競爭對手」提出最刁鑽的挑戰：
- 這個痛點真的是客群的首要痛點，還是分析師的假設？[需驗證]
- 現有廠商為何沒有解決這個痛點？是選擇不做，還是真的有技術障礙？
- 這個機會是否已被 Qualcomm/MediaTek 先佔？供應鏈依賴風險？
- 技術成熟度與市場時機是否匹配？

每個挑戰後提供「應對策略」，策略必須對應到具體的機制，不能只說「持續研究」。

---

## 任務四：本週關鍵數字

只引用文章中明確出現的數字，不捏造。格式：數字｜來源｜日期｜意涵。

---

請用繁體中文輸出，保留英文技術術語。每個任務分開輸出，格式清晰。"""


def run_trend_analysis(client, articles: list[dict]) -> str:
    """Call Claude Opus to run full trend analysis. Returns markdown text."""
    article_summary = _format_articles_for_prompt(articles, max_per_cat=15)
    prompt = TREND_PROMPT.format(article_summary=article_summary)

    print(f"  → Sending {len(articles)} articles to Claude {MODEL_TREND}...")
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL_TREND,
                max_tokens=8000,
                system=TREND_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception as e:
            err = str(e)
            if "529" in err or "overloaded" in err.lower():
                wait = 30 * (2 ** attempt)   # 30s → 60s → 120s → 240s
                print(f"  ⚠ API overloaded (attempt {attempt+1}/4), retry in {wait}s...")
                import time; time.sleep(wait)
            else:
                return f"⚠️ Analysis failed: {e}"
    return "⚠️ Analysis failed: API overloaded after 4 retries"


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
                     analysis_text: str, trend_url: str = ""):
    """Send Slack notification for weekly trend report."""
    import urllib.request

    preview = analysis_text[:400].replace("\n", " ").replace('"', '\\"')
    report_url = trend_url or PAGES_URL

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
                        "url": report_url
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🏠 Dashboard"},
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
        trend_url = f"{PAGES_URL}/{trend_fname}"
        send_slack_trend(webhook, today, len(articles), analysis, trend_url=trend_url)

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
