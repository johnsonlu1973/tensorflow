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

### 五個核心概念精確定義（作答前必須對照確認，不符合定義的不算）

| 概念 | 精確定義 | 本質 | 關鍵邊界 |
|------|---------|------|---------|
| **產業趨勢** | 宏觀長期不可逆的結構性轉變 | 「遊戲規則的改變」 | ❌ 不能直接變現；❌ 不是短期市場波動 |
| **市場新機會** | 趨勢造成的、尚未被現有競爭者充分滿足的特定商業空間 | 「潛在的戰場」 | ✅ 必須有可定義邊界；❌ 不是泛稱「需求增加」 |
| **痛點** | 目標客戶完成特定 JTBD 時遭遇的、現有方案無法妥善處理的具體阻礙 | 「切入市場的破口」 | ✅ 痛點越深支付意願越高；❌ 不是功能需求清單 |
| **客戶價值** | 解決痛點後的〔總體效益 − 總體成本（金錢＋時間＋學習）〕 | 「客戶買單的理由」 | ✅ 向外交付給客戶；❌ 不等於商業價值 |
| **商業價值** | 企業能擷取的財務指標＋戰略資產（高毛利／市佔／專利／生態護城河） | 「公司留住的利潤與壁壘」 | ❌ 不等於客戶價值；需要護城河才能持續擷取 |

---

### 四層因果框架（每層輸入必須符合上方精確定義，否則標 [未驗證]）

**🔵 啟動層：產業趨勢 ──→ 市場新機會**
（遊戲規則改變，潛在戰場浮現）
推演範例：大語言模型微型化（宏觀不可逆轉變：運算範式位移）→ 打破了「AI 必須依賴雲端」的市場平衡 → 「App-less、AI Agent 原生 OS 平台」商業空間出現（邊界：行動端 Agent 協作，競爭者尚未充分滿足）。

**🟡 鎖定層：市場新機會 ──→ 痛點**
（潛在戰場，找到切入破口）
推演範例：在上述商業空間中，設備製造商的 JTBD 是「讓多 Agent 常駐背景協作」→ 現有 SoC 架構造成 KV Cache 頻寬瓶頸＋功耗爆炸（現有方案無法妥善處理的具體阻礙）。

**🟢 轉換層：痛點 ──→ 客戶價值**
（切入破口，形成客戶買單的理由）
推演範例：創新 SoC 記憶體壓縮架構消除 KV Cache 瓶頸 → 客戶效益：無延遲、隱私保護、零雲端依賴的 AI 體驗；客戶成本：與現有旗艦 ASP 相近。效益 > 成本 → 客戶價值為正。

**🔴 收成層：客戶價值 ──→ 商業價值**
（客戶買單的理由，轉化為公司留住的利潤與壁壘）
推演範例：獨家架構壁壘（護城河）→ 高 ASP 定價能力（財務）＋軟硬整合生態綁定（戰略資產）→ 市佔擴大＋高毛利（商業價值持續）。

---

找出 2-3 個最重要的結構性機會。每個機會**必須按四層順序**回答因果問題，每層先確認輸入符合定義，再作答：

**🔵 啟動層：產業趨勢 ──→ 市場新機會**
> ❓ 因果問題（必答）：
> 1. 這個宏觀結構性轉變是否為「長期不可逆」？改變了哪個遊戲規則（技術可行性／成本曲線／法規／供需結構）？
> 2. 為什麼它使得一個「尚未被現有競爭者充分滿足的特定商業空間」此時才浮現？邊界是什麼（誰、做什麼、在哪個場景）？
> 3. 若趨勢有反轉風險，標記 [未驗證] 並說明條件。
- 產業趨勢：（說明這是什麼宏觀結構性轉變；確認三個條件：① 宏觀 — 影響整個產業而非單一公司；② 長期 — 5年以上驅動力；③ 不可逆 — 即使短期受阻仍會繼續；三個條件若任一無法確認，標 [未驗證]）
- 趨勢佐證：（引用具體文章 [來源 日期] 作為觀察依據；非直接等於趨勢本身）
- 機會邊界：（精確描述商業空間，不能只說「需求增加」）
- 因果回答：（說明趨勢→機會的打破平衡機制）

**🟡 鎖定層：市場新機會 ──→ 痛點**
> ❓ 因果問題（必答）：
> 1. 在這個商業空間中，目標客戶試圖完成的具體 JTBD 是什麼？
> 2. 他們在完成這個 JTBD 時遭遇什麼具體阻礙？現有方案（Qualcomm／MediaTek／OEM）的哪個具體缺陷（速度／精度／成本／架構限制）導致阻礙無法消除？
> 3. 這個痛點多深？支付意願估計？（越具體越好；泛稱「需求增加」不算痛點）
- 目標客群與 JTBD：（確認符合「現有方案無法妥善處理」的定義）
- 因果回答：（說明具體阻礙的技術或商業機制）

**🟢 轉換層：痛點 ──→ 客戶價值**
> ❓ 因果問題（必答）：
> 1. 這個解決方案如何消除上述痛點（具體技術或商業機制）？
> 2. 消除後，客戶獲得的「總體效益」是什麼？客戶須付出的「總體成本（金錢＋時間＋學習）」是多少？為何效益 > 成本？
> 3. 為何現有廠商目前無法提供同等客戶價值？（技術壁壘？時間窗口？生態位置？成本結構？若能輕易複製，標 [未驗證]）
- 解決方案：
- 因果回答：（說明客戶價值 = 效益 − 成本的具體構成；確認向外交付給客戶）

**🔴 收成層：客戶價值 ──→ 商業價值**
> ❓ 因果問題（必答）：
> 1. 這個商業模式如何將「客戶買單的理由」轉化為公司能擷取的「財務指標＋戰略資產」？
> 2. 定價權從哪裡來（架構壁壘／生態綁定／高轉換成本）？客戶為何不轉向競品？
> 3. 護城河會隨時間加深還是消失？若客戶價值無法轉化為商業價值，明確標記 [未驗證] 並說明風險。
- 商業模式：
- 因果回答：（說明價值擷取的具體機制及護城河類型；確認商業價值 ≠ 客戶價值）
- 預估市場規模與時間窗口：（標記資料時間 [來源：XXX，YYYY.MM]）

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
