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

## 規則二：因果鏈的四個強制問題

寫出「A → B」之前，必須依序回答以下四個問題。
缺少任何一個問題的回答 = 因果不成立，必須標記 [未驗證]。

  Q1. 條件變化：A 中的「什麼具體條件」在「何時」發生了改變？
      （不是「A 存在」，是「A 的什麼改變了」）
  Q2. 傳導機制：這個條件變化透過「什麼具體物理/經濟/行為機制」影響到 B？
      （必須有動詞，說明能量/資訊/誘因如何從 A 傳到 B）
  Q3. 門檻條件：為什麼這個機制在「此時」足以引發 B？
      （說明臨界點：什麼條件讓此時「夠了」，而兩年前「不夠」）
  Q4. 反事實測試：如果把 A 拿掉，B 還會發生嗎？
      （如果還會發生，你的因果是假的；必須說明「拿掉 A 後 B 為何消失」）

---
## 規則三：客群浮現必須用機制說明，不能用存在說明

寫出「目標客群是 X」之前，必須回答：
  - 為什麼是 X，而不是 Y 或 Z？
  - X 的什麼「結構性條件」使他們在此時成為最有支付意願的客群？
  - 有能力解決這個問題的廠商為什麼還沒解決？
    （是選擇不做？技術障礙？利益衝突？商業模式不符？）

---

## 規則四：修正時明確列出不受影響的分析

修正一個錯誤結論時，輸出格式必須包含：
修正：[原主張]
原因：[哪裡出錯]
不受影響：[哪些分析和本次修正無關，仍然有效]
「不受影響」這一行不能省略。

---

## 規則五：時效性敏感的主張標記資料時間

市場數據、標準進度、產品規格、競品動態等可能過期的主張，
必須標記資料時間：[來源：XXX，2025.03]
時間不明時標：[時間不明，建議搜尋確認]
---
## 因果推理的最高原則：反事實測試

每個「→」箭頭寫完後，在心裡執行：
「如果我把左側的 A 完全拿掉，右側的 B 還會發生嗎？」
- 如果答案是「會」→ 你的因果是假的，A 不是真正原因
- 如果答案是「不會，因為 ___」→ 填入這個「因為」，這才是你的因果機制

這個測試不需要寫入輸出，但必須內部執行"""


TREND_PROMPT = """請分析以下過去一週的市場情報摘要，完成三項分析任務。
套用 System Prompt 的全部規則。每個「→」箭頭必須通過四個強制問題（Q1-Q4）。

{article_summary}

---

## 任務一：結構性機會偵測（Structural Opportunity Detection）

### 重要指令：這是推導題，不是填空題

你不是在「填入四個欄位」。
你是在「從事實一步一步推導到商業結論」。
每一層的輸出，必須是「上一層的邏輯結果」，不能是「平行的新觀察」。

---

### 四層因果框架：精確定義（先閱讀，再作答）

| 概念 | 精確定義 | ❌ 常見錯誤 |
|------|---------|-----------|
| 產業趨勢 | 宏觀長期不可逆的結構性轉變——「遊戲規則的改變」 | ❌ 不是「需求增加」❌ 不是短期波動 |
| 市場新機會 | 趨勢造成的、現有競爭者尚未充分滿足的特定商業空間 | ❌ 不是「需求存在」❌ 必須有可定義邊界 |
| 痛點 | 目標客群完成特定 JTBD 時，現有方案造成的具體阻礙 | ❌ 不是功能需求清單 ❌ 不是「體驗不好」 |
| 客戶價值 | 解決痛點後的（總效益 − 總成本），向外交付給客戶 | ❌ 不等於商業價值 |
| 商業價值 | 企業能擷取的財務指標＋戰略資產，需要護城河才能持續 | ❌ 不等於客戶價值 |

---

找出 2-3 個最重要的結構性機會。每個機會按以下格式作答。

⚠️ 格式指令：
- 每個問題獨立回答，不要合併
- 每個回答必須是「推導的結果」，不能是「平行的觀察」
- 所有箭頭必須通過 Q1-Q4 四個問題
- 客群說明必須通過規則三（為什麼是這個客群，不是其他客群）

---

**機會 [編號]：[用一句話描述機會的本質]**

#### Step 1：事實觀察（只列事實，嚴禁在此步驟下結論）

列出 3-5 個本週文章中的具體現象。格式：
- [來源，日期]「直接引文或精確摘要」→ 觀察到的事實是：___

#### Step 2：條件變化分析（從 Step 1 的事實中找出「什麼改變了」）

從上方觀察中，找出「相較於過去，此時出現了什麼具體的條件變化」。

回答以下問題（不得跳過）：
- 哪個條件在什麼時間點發生了改變？（不是「存在」，是「改變」）
- 這個改變是技術性的、經濟性的，還是監管性的？
- 這個改變在多久前不存在？（說明時間點，確立「此時」的意義）
- [推斷/來源] 標記

#### Step 3：趨勢導出（從 Step 2 的條件變化中推導趨勢）

⚠️ 不能直接陳述趨勢。必須先回答：

- Step 2 中的條件變化，透過什麼機制（Q2）影響了整個產業的運作方式？
- 這個機制為什麼在此時足以造成不可逆的結構性轉變（Q3）？
- 反事實：如果 Step 2 的條件變化沒有發生，這個趨勢還會存在嗎？說明為什麼（Q4）。
- 才能陳述：「因此，產業趨勢是：___」

驗證：
- ✅ 宏觀性：影響整個產業而非單一公司？
- ✅ 長期性：5 年以上驅動力？
- ✅ 不可逆性：即使短期受阻仍會繼續？
任一 ❌ 則標記 [未驗證]

#### Step 4：市場新機會浮現（從 Step 3 的趨勢中推導機會）

⚠️ 不能直接陳述機會。必須先回答：

- Step 3 的趨勢改變了哪個具體的「競爭條件」（Q1）？
  （不是「需求增加」，是「原本不存在的商業空間因為什麼原因出現了」）
- 這個競爭條件的改變，透過什麼機制（Q2）使新的商業空間在此時出現？
- 為什麼現有競爭者沒有充分滿足這個空間？
  （說明結構性原因：利益衝突？架構鎖定？商業模式不符？）
- 反事實：如果趨勢不存在，這個商業空間還會出現嗎？（Q4）
- 才能陳述：「因此，市場新機會是：___（誰、做什麼、在哪個場景）」

#### Step 5：目標客群與 JTBD（從 Step 4 的機會中推導誰最先有需求）

⚠️ 不能直接說「目標客群是 X」。必須先回答規則三的三個問題：

問題 A：為什麼是 X，而不是其他看似相關的客群？
  - 列出 2-3 個「看似相關但排除」的客群
  - 逐一說明為什麼他們「不是」最先有支付意願的客群
  - 才能確立「因此 X 是目標客群，因為 ___」

問題 B：X 的什麼「結構性條件」使他們有支付意願？
  - 不是「他們有需求」，是「他們的什麼處境使他們願意付錢」
  - 說明支付意願的具體來源（差異化壓力、合規壓力、成本壓力？）

問題 C：有能力解決這個問題的廠商為什麼還沒解決？
  - 選擇不做（利益衝突：解決了會傷害自己現有收入）？
  - 技術障礙（什麼技術障礙？需要多久才能克服）？
  - 商業模式不符（他們的獲利模式不適合這個客群）？
  必須選擇一個並說明機制

- 才能陳述：「因此，JTBD 是：___（在什麼情境下，完成什麼任務，達到什麼標準）」

#### Step 6：痛點（從 Step 5 的 JTBD 中推導具體阻礙）

⚠️ 不能直接說「痛點是 X」。必須先回答：

- 目標客群在執行 Step 5 的 JTBD 時，在哪個具體環節遇到阻礙？
  （速度？精度？成本？架構限制？）
- 現有方案在這個環節為什麼無法改善？
  （說明技術/經濟/架構機制：不是「未優化」，是「為什麼無法優化」）
- 反事實：如果現有方案能解決這個阻礙，目標客群還會尋找新方案嗎？（Q4）
- 痛點有多深？（支付意願的量化估計，或至少排序）

- 才能陳述：「因此，核心痛點是：___」

#### Step 7：客戶價值（從 Step 6 的痛點中推導解決方案的價值）

⚠️ 格式：先描述解決方案（一句話），再逐項回答：

- 機制：解決方案如何消除 Step 6 的痛點？（具體技術或商業機制，有動詞）
- 效益：客戶獲得的「總體效益」是什麼？（定量優先，說明量化基礎）
- 成本：客戶須付出的「總體成本（金錢＋時間＋學習）」是多少？
- 效益 > 成本 的機制：為什麼效益超過成本？（說明比較基礎）
- 競爭壁壘：為什麼現有廠商此時無法提供同等客戶價值？
  （說明時間窗口：多久後現有廠商能提供？窗口有多寬？）
- 反事實：如果痛點不存在，這個解決方案還有客戶價值嗎？（Q4）

#### Step 8：商業價值（從 Step 7 的客戶價值中推導公司能擷取的利潤）

⚠️ 格式：先描述商業模式（一句話），再逐項回答：

- 擷取機制：如何將客戶價值轉化為財務指標＋戰略資產？（具體機制）
- 定價權來源：定價權從哪裡來？（架構壁壘、生態綁定、高轉換成本？）
  說明轉換成本的具體組成（工程時間、資料遷移、學習成本？）
- 護城河動態：護城河是會隨時間加深，還是削弱？
  - 加深的機制是什麼？
  - 削弱的威脅是什麼？
  - 什麼時間點是護城河的頂峰？
- 商業價值上限：如果護城河在 N 年後消失，公司能在窗口內擷取多少價值？
- 預估市場規模與時間窗口：[來源：XXX，YYYY.MM] 或 [未驗證，建議搜尋確認]

---

### ✅ 任務一因果鏈完整性審核（完成 Step 1-8 後必須執行）

列出你在 Step 1-8 中寫過的每一個「→」箭頭，填入下表：

| # | 箭頭（A → B） | Q1: A 中什麼條件變化了？ | Q2: 傳導機制是什麼？ | Q3: 為何此時足夠？ | Q4: 拿掉A，B還會發生？ | 通過？ |
|---|-------------|----------------------|-------------------|-----------------|----------------------|------|

判斷標準：
- ✅ = 四個問題都有實質回答
- ❌ = 任何一個問題的回答是「因為有需求」「因為趨勢」「因為明顯」等無機制說明

若有 ❌：明確指出，補充機制，或改標 [未驗證] 並說明缺什麼資訊才能驗證。

---

比對海外媒體 vs 台灣媒體的報導落差：
- 是否有「海外說需求放緩，台灣供應鏈卻在增產」的矛盾？
- 是否有技術路線的分歧？

每個矛盾點依以下格式輸出：
1. 矛盾現象：海外報導說 ___ vs 台灣報導說 ___
2. 可能原因（必須列出至少兩個競爭性解釋，標記 [推斷] 或 [未驗證]）：
   - 解釋 A：___（機制是：___）
   - 解釋 B：___（機制是：___）
3. 哪個解釋目前更有支撐？為什麼？
4. 對 SoC 規劃的影響：___
5. 建議監測指標：___（具體可觀察的數據，不是「持續關注」）

---

## 任務三：Red Teaming（對抗性提問）

針對任務一的每個機會，扮演「最了解這個市場的反方競爭對手」提出挑戰。

每個挑戰必須是「機制性挑戰」，不是「可能性挑戰」：
- ❌ 「這個機會可能不存在」（沒有機制）
- ✅ 「因為 X 機制的存在，這個機會實際上已被 Y 佔據，原因是 Z」

強制挑戰清單（每個都要回答，不能跳過）：

挑戰 1：客群痛點驗證
  - 這個痛點是客群「實際行為顯示的第一優先痛點」，
    還是分析師從外部觀察推斷的痛點？
  - 如果是推斷，用什麼具體方法可以在 4 週內驗證？

挑戰 2：既有廠商行為解釋
  - 現有大廠（Qualcomm/MediaTek/NVIDIA）沒有解決這個問題，
    最可能的原因是哪一個？
    A. 他們不知道（資訊不對稱）
    B. 他們知道但選擇不做（利益衝突）
    C. 他們試過但技術上做不到（技術障礙）
    D. 他們正在做但還沒公開（時間問題）
  - 選擇最可能的選項，說明機制，說明對此機會的影響。

挑戰 3：機會時間窗口
  - 如果大廠選擇 D（正在做），最快什麼時候會公開？
  - 這個時間窗口是否足夠建立可持續的護城河？
  - 如果不足夠，這個機會的商業價值上限是多少？

挑戰 4：供應鏈與地緣政治風險
  - 這個機會的實現依賴哪些關鍵供應鏈節點？
  - 哪個節點最脆弱？脆弱的機制是什麼？

每個挑戰後，提供「應對策略」：
  - 策略必須對應到挑戰的具體機制
  - 必須說明「做了這個策略之後，挑戰的機制會如何被改變」
  - ❌ 不接受「持續研究」「加強關注」等無機制的策略

---

## 任務四：本週關鍵數字

只引用文章中明確出現的數字，不捏造。
格式：數字｜來源｜日期｜意涵（這個數字說明了什麼機制或臨界點）

---

請用繁體中文輸出，保留英文技術術語。每個任務分開輸出，格式清晰。"""


def run_trend_analysis(client, articles: list[dict]) -> str:
    """Call Claude Opus to run full trend analysis.
    
    v4.0 改動：
    - 第一輪：完整分析
    - 第二輪：因果鏈審核（針對第一輪輸出中所有「→」做反事實測試）
    - 合併輸出
    """
    article_summary = _format_articles_for_prompt(articles, max_per_cat=15)
    prompt = TREND_PROMPT.format(article_summary=article_summary)

    print(f"  → Sending {len(articles)} articles to Claude {MODEL_TREND}...")

    def _call_claude(messages: list[dict], max_tokens: int = 8000) -> str:
        for attempt in range(4):
            try:
                resp = client.messages.create(
                    model=MODEL_TREND,
                    max_tokens=max_tokens,
                    system=TREND_SYSTEM,
                    messages=messages,
                )
                return resp.content[0].text
            except Exception as e:
                err = str(e)
                if "529" in err or "overloaded" in err.lower():
                    import time
                    wait = 30 * (2 ** attempt)
                    print(f"  ⚠ API overloaded (attempt {attempt+1}/4), retry in {wait}s...")
                    time.sleep(wait)
                else:
                    return f"⚠️ Analysis failed: {e}"
        return "⚠️ Analysis failed: API overloaded after 4 retries"

    # ── 第一輪：完整分析 ──────────────────────────────────────────────
    print(f"  → Round 1: Full trend analysis...")
    first_pass = _call_claude([{"role": "user", "content": prompt}])

    if first_pass.startswith("⚠️"):
        return first_pass

    print(f"  ✓ Round 1 complete ({len(first_pass)} chars)")

    # ── 第二輪：因果鏈反事實審核 ────────────────────────────────────────
    # 只針對任務一的因果鏈做專項審核
    # 避免 Claude 重新生成全部內容（節省 token，聚焦審核）
    review_prompt = """請針對你剛才在「任務一」中寫的所有「→」箭頭，執行以下審核。

## 審核指令

從你的任務一輸出中，找出每一個「→」箭頭（包含文字描述中的因果關係，不只是符號「→」）。

對每個因果關係，執行「反事實測試」：
「如果把左側的 A 完全拿掉，右側的 B 還會發生嗎？」

輸出格式（每個箭頭一行）：

| 箭頭 | 反事實：拿掉A後B是否消失？ | 消失的機制 | 判定 |
|------|--------------------------|-----------|------|
| X → Y | 消失，因為___ | ___ | ✅ 因果成立 |
| X → Y | 不消失，因為___ | ___ | ❌ 因果不成立，需修正 |

## 修正指令

對所有判定為 ❌ 的箭頭：
1. 說明原因：為什麼這個因果不成立？
2. 提供修正：重新陳述正確的因果關係（或標記 [未驗證] 並說明缺什麼資訊）
3. 引用規則四格式：
   修正：[原主張]
   原因：[哪裡出錯]
   不受影響：[哪些分析和本次修正無關，仍然有效]

## 重要指令

- 不需要重新輸出任務一的全部內容
- 只輸出審核表格和必要的修正
- 如果所有箭頭都通過，只需輸出「✅ 所有因果鏈通過反事實測試」"""

    print(f"  → Round 2: Causal chain review...")
    review = _call_claude(
        messages=[
            {"role": "user",    "content": prompt},
            {"role": "assistant","content": first_pass},
            {"role": "user",    "content": review_prompt},
        ],
        max_tokens=4000,
    )
    print(f"  ✓ Round 2 complete ({len(review)} chars)")

    # ── 合併輸出 ─────────────────────────────────────────────────────
    separator = "\n\n---\n\n## 🔍 第二輪：因果鏈反事實審核結果\n\n"
    return first_pass + separator + review

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
.kn-table {
  width: 100%; border-collapse: collapse; font-size: 0.85em;
  margin: 8px 0 16px;
}
.kn-table th {
  background: #1f2937; color: var(--yellow); font-weight: 600;
  padding: 7px 12px; text-align: left; border-bottom: 2px solid var(--border);
  white-space: nowrap;
}
.kn-table td {
  padding: 6px 12px; border-bottom: 1px solid var(--border);
  vertical-align: top; line-height: 1.5;
}
.kn-table tr:last-child td { border-bottom: none; }
.kn-table tr:hover td { background: rgba(255,255,255,0.03); }
.kn-table td:first-child { color: var(--text-bright); font-weight: 600; white-space: nowrap; }
"""

def _pipe_lines_to_table(lines: list[str]) -> str:
    """Convert pipe-delimited lines to an HTML table. Skip markdown separator rows (---|---)."""
    rows = []
    for line in lines:
        stripped = line.strip().strip("｜|")
        cells = [c.strip() for c in re.split(r"[｜|]", stripped)]
        if all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue  # markdown separator row
        rows.append(cells)
    if not rows:
        return ""
    is_header = lambda r: any(kw in "".join(r) for kw in ("數字", "來源", "日期", "意涵", "number", "source"))
    header, body = (rows[0], rows[1:]) if is_header(rows[0]) else (None, rows)
    def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = ['<table class="kn-table">']
    if header:
        html.append("<thead><tr>" + "".join(f"<th>{esc(c)}</th>" for c in header) + "</tr></thead>")
    html.append("<tbody>")
    for row in body:
        html.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>")
    html.append("</tbody></table>")
    return "\n".join(html)


def _process_analysis_html(text: str) -> str:
    """Convert pipe-table blocks in analysis text to HTML tables; escape rest for pre-wrap."""
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = text.split("\n")
    output = []
    table_buf = []

    def flush_table():
        if table_buf:
            output.append(_pipe_lines_to_table(table_buf))
            table_buf.clear()

    for line in lines:
        # A pipe-table line has 2+ pipe characters (｜ or |)
        if len(re.findall(r"[｜|]", line)) >= 2:
            table_buf.append(line)
        else:
            flush_table()
            output.append(esc(line))

    flush_table()
    return "\n".join(output)


def _render_trend_html(date: str, analysis_text: str, articles: list[dict],
                        period_days: int) -> str:
    by_cat = _build_category_summary(articles)
    total  = len(articles)

    cat_pills = ""
    for cat, arts in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        emoji, label = CATEGORY_LABEL.get(cat, ("📰", cat))
        cat_pills += f'<span class="cat-pill">{emoji} {label} {len(arts)}</span>'

    # Split first-pass analysis from second-round causal review
    REVIEW_SEP = "## 🔍 第二輪：因果鏈反事實審核結果"
    if REVIEW_SEP in analysis_text:
        main_analysis, review_section = analysis_text.split("---\n\n" + REVIEW_SEP, 1)
        pass_count = analysis_text.count("✅ 因果成立") + analysis_text.count("✅ 所有因果鏈")
        fail_count = analysis_text.count("❌ 因果不成立")
        badge_color = "#3fb950" if fail_count == 0 else "#e3b341" if fail_count < 3 else "#f85149"
        audit_stat = f'<div class="stat-box" style="border-color:{badge_color}"><div class="label">因果審核</div><div class="value" style="color:{badge_color};font-size:1em">✅{pass_count} ❌{fail_count}</div></div>'
        review_html = f'\n<h2>🔍 因果鏈反事實審核</h2>\n<div class="analysis-body">{_process_analysis_html(review_section)}</div>'
    else:
        main_analysis = analysis_text
        audit_stat    = ""
        review_html   = ""

    processed = _process_analysis_html(main_analysis)

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
  {audit_stat}
</div>

<div class="cat-breakdown">{cat_pills}</div>

<h2>🔍 Claude Opus 深度分析</h2>
<div class="analysis-body">{processed}</div>
{review_html}

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
