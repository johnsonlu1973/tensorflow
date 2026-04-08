"""HTML report generator v3 — bilingual cards, Read Full Text + Deep Analysis buttons.

Card design per article:
  ┌──────────────────────────────────────────────┐
  │ [Source] [Date]          [Category]          │
  │ Title (EN)                                   │
  │ 標題（中文）                                  │
  │ RSS summary (EN) / RSS 摘要（中文）           │
  │                                              │
  │ [🔗 閱讀全文]  [📋 貼上全文 ▼]  [⭐ 加入關注] │
  │ ┌─ textarea (hidden until click) ──────────┐ │
  │ │ 請貼上文章全文...                         │ │
  │ │                              [💾 儲存]   │ │
  │ └──────────────────────────────────────────┘ │
  │ [🔬 深度分析]  (enabled after full text saved)│
  └──────────────────────────────────────────────┘
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT     = Path(__file__).parent
DOCS_DIR = ROOT.parent / "docs"
ARCHIVE_ANALYSIS_DIR = ROOT / "archive" / "analysis"

GITHUB_REPO   = "johnsonlu1973/tensorflow"
GITHUB_BRANCH = "master"
PAGES_URL     = "https://johnsonlu1973.github.io/tensorflow"

TW_TZ = timezone(timedelta(hours=8))

CATEGORY_LABEL = {
    "chips_soc":   ("💾", "Chips / SoC"),
    "mobile":      ("📱", "Mobile"),
    "agentic_ai":  ("🤖", "Agentic AI"),
    "5g_cpe":      ("📡", "5G / CPE"),
    "csp_cloud":   ("☁️", "CSP / Cloud"),
    "tech_general":("🌐", "Tech"),
    "taiwan":      ("🇹🇼", "台灣"),
}

ANALYSIS_PROMPT_TEMPLATE = """你是 SoC 產品規劃專家。請用「4 層因果鏈分析框架」分析以下文章，以繁體中文為主、英文技術術語保留原文，輸出中英文並列格式。

## 文章資訊
標題：{title}
來源：{source}
日期：{date}

## 全文
{fulltext}

---

## 4 層分析框架

### 🔵 啟動層：趨勢 → 市場新機會
**產業趨勢**：（原文依據）
**市場新機會**：（打破了什麼現有平衡？）

### 🟡 鎖定層：機會 → 目標客群與痛點
**目標客群**：
**最急迫的痛點**：
**現有方案不足**：

### 🟢 轉換層：痛點 → 客戶價值
**解決方案**：
**差異化優勢**：
**客戶價值**：

### 🔴 收成層：客戶價值 → 商業價值
**商業模式**：
**護城河**：
**商業價值**：

### 🗺 產業鏈結構圖
（ASCII 圖，從終端用戶到上游）

### ⛓ 產業鏈誘因分析
| 產業層級 | 誘因來源 | 誘因強度 | 潛在障礙 | 態度 |

⚠️ 資料規則：只引用文章中明確出現的數字。如果文章資訊不足，請標註（原文未提及）並說明需要補充搜尋哪些資訊。"""

# ---------------------------------------------------------------------------
# Hot News helpers
# ---------------------------------------------------------------------------

HOT_KEYWORDS_EN = {
    "ban", "sanction", "tariff", "embargo", "restriction", "breakthrough",
    "acquisition", "merger", "warning", "crisis", "record", "critical", "launch",
}
HOT_KEYWORDS_ZH = {
    # 只保留具體且不易被翻譯雙重計分的詞
    "禁令", "制裁", "關稅", "突破", "收購", "合併", "警告", "禁止",
}
HOT_SOURCES = {"Bloomberg", "Reuters", "電子時報", "SemiAnalysis", "Digitimes"}

# Tech keywords: each hit +1 (relevance signal, not urgency)
TECH_KEYWORDS = {
    "ai", "5g", "6g", "soc", "tops", "latency", "ghz",
    "tokens", "benchmark", "orchestration", "multi-agent",
}


def _importance_score(article: dict) -> int:
    score = 0
    title_en = article.get("title", "").lower()
    title_zh = article.get("title_zh", "")

    # EN keywords → only check EN title (avoid double-count via translation)
    for kw in HOT_KEYWORDS_EN:
        if kw in title_en:
            score += 2

    # ZH keywords → only check ZH title
    for kw in HOT_KEYWORDS_ZH:
        if kw in title_zh:
            score += 2

    # Tech keywords → check both (technical terms less likely to double-count)
    combined = title_en + " " + title_zh.lower()
    for kw in TECH_KEYWORDS:
        if kw in combined:
            score += 1

    if article.get("source", "") in HOT_SOURCES:
        score += 1
    return score


def _load_user_interest() -> list:
    """Load articles from archive/fulltext/ and archive/bookmarks/."""
    articles = []
    for subdir in ("fulltext", "bookmarks"):
        d = ROOT / "archive" / subdir
        if d.exists():
            for f in sorted(d.glob("*.json"), reverse=True)[:30]:
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    data["_interest_type"] = subdir
                    articles.append(data)
                except Exception:
                    pass
    # Deduplicate by URL
    seen, result = set(), []
    for a in articles:
        url = a.get("url", "")
        if url and url not in seen:
            seen.add(url)
            result.append(a)
    return result[:15]


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
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
  padding: 16px 12px; max-width: 900px; margin: 0 auto; line-height: 1.6;
}
h1 { color: var(--blue); font-size: 1.2em; margin-bottom: 4px; }
.page-meta { color: var(--text-dim); font-size: 0.8em; margin-bottom: 20px; }

/* ── Category header ── */
.cat-header {
  display: flex; align-items: center; gap: 8px;
  margin: 24px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px;
}
.cat-header h2 { color: var(--text-bright); font-size: 1em; }
.cat-count { color: var(--text-dim); font-size: 0.8em; }

/* ── Article card ── */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; margin-bottom: 10px; overflow: hidden;
}
.card-head { padding: 12px 14px; }
.card-meta-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 6px; flex-wrap: wrap;
}
.source-tag {
  font-size: 0.72em; font-weight: 700; padding: 2px 8px;
  border-radius: 10px; background: #21262d; color: var(--text-dim);
  white-space: nowrap;
}
.date-tag { font-size: 0.72em; color: var(--text-dim); }
.lang-tag {
  font-size: 0.68em; padding: 1px 6px; border-radius: 8px;
  background: #1a3a5c; color: #79c0ff;
}

/* ── Bilingual title ── */
.title-en {
  font-size: 0.9em; font-weight: 600; color: var(--text-bright);
  line-height: 1.4; margin-bottom: 2px;
}
.title-en a { color: inherit; text-decoration: none; }
.title-en a:hover { color: var(--blue); }
.title-zh {
  font-size: 0.85em; color: var(--text-dim); line-height: 1.4;
  margin-bottom: 8px;
}

/* ── Bilingual summary ── */
.summary-block { margin-bottom: 10px; }
.summary-en {
  font-size: 0.8em; color: var(--text-dim); line-height: 1.5;
  border-left: 2px solid var(--border); padding-left: 8px; margin-bottom: 4px;
}
.summary-zh {
  font-size: 0.8em; color: #79c0ff; line-height: 1.5;
  border-left: 2px solid #1a3a5c; padding-left: 8px;
}

/* ── Action buttons ── */
.card-actions {
  display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 2px;
}
.btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 5px 12px; border-radius: 6px; font-size: 0.78em;
  font-weight: 600; cursor: pointer; border: 1px solid; text-decoration: none;
  transition: opacity 0.15s; white-space: nowrap;
}
.btn:hover { opacity: 0.8; }
.btn-read {
  background: #0d1926; border-color: var(--blue); color: var(--blue);
}
.btn-paste {
  background: #1a1300; border-color: var(--yellow); color: var(--yellow);
}
.btn-analyze {
  background: #1a0d0d; border-color: var(--red); color: var(--red);
  opacity: 0.4; cursor: not-allowed;
}
.btn-analyze.enabled {
  opacity: 1; cursor: pointer;
}
.btn-save {
  background: #0d1a12; border-color: var(--green); color: var(--green);
}
.btn-copy-prompt {
  background: #1a1326; border-color: var(--purple); color: var(--purple);
}

/* Bookmark button */
.btn-bookmark {
  background: #1a1400; border-color: #e8a317; color: #e8a317;
}
.btn-bookmark.bookmarked { opacity: 0.5; cursor: default; }

/* ── Full text panel ── */
.fulltext-panel {
  display: none; border-top: 1px solid var(--border);
  padding: 12px 14px; background: #0d1117;
}
.fulltext-panel.open { display: block; }
.panel-label {
  font-size: 0.72em; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--yellow); margin-bottom: 6px;
}
.fulltext-area {
  width: 100%; min-height: 160px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.82em; padding: 10px;
  font-family: inherit; line-height: 1.6; resize: vertical;
}
.fulltext-area:focus { outline: none; border-color: var(--yellow); }
.panel-actions {
  display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;
  align-items: center;
}
.save-status { font-size: 0.75em; color: var(--text-dim); }
.save-status.ok  { color: var(--green); }
.save-status.err { color: var(--red); }

/* ── Analysis prompt panel ── */
.analysis-panel {
  display: none; border-top: 1px solid var(--border);
  padding: 12px 14px; background: #0d0d17;
}
.analysis-panel.open { display: block; }
.prompt-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px; font-size: 0.78em;
  color: var(--text-dim); white-space: pre-wrap; max-height: 300px;
  overflow-y: auto; line-height: 1.6; margin-bottom: 8px;
}

/* ── Back link ── */
.back { color: var(--blue); text-decoration: none; font-size: 0.82em;
        display: inline-block; margin-bottom: 14px; }
.back:hover { text-decoration: underline; }

/* ── Index cards ── */
.index-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 16px; margin-bottom: 10px;
  text-decoration: none; display: block;
  transition: border-color 0.15s, background 0.15s;
}
.index-card:hover { border-color: var(--blue); background: #1c2128; }
.index-card h2 { color: var(--blue); font-size: 0.95em; margin-bottom: 4px; }
.index-card .card-meta { color: var(--text-dim); font-size: 0.8em; }
.new-count { color: var(--green); font-weight: 600; }

/* ── Token config banner ── */
.token-banner {
  background: #1a1300; border: 1px solid var(--yellow); border-radius: 8px;
  padding: 10px 14px; margin-bottom: 16px; font-size: 0.82em;
}
.token-banner strong { color: var(--yellow); }
.token-input {
  background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
  color: var(--text); padding: 4px 8px; font-size: 0.9em; width: 320px;
  margin: 4px 0;
}
.token-input:focus { outline: none; border-color: var(--yellow); }

/* ── Hot News section ── */
.hot-section {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;
}
.hot-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  border-bottom: 1px solid var(--border); padding-bottom: 6px;
}
.hot-header h2 { color: var(--text-bright); font-size: 0.95em; margin: 0; }
.hot-icon { font-size: 1.1em; }
.hot-count { color: var(--text-dim); font-size: 0.75em; margin-left: auto; }
.hot-card {
  display: block; padding: 8px 10px; border-radius: 6px;
  text-decoration: none; margin-bottom: 6px;
  border-left: 2px solid var(--border);
  transition: border-color 0.15s, background 0.15s;
}
.hot-card:hover { border-color: var(--blue); background: #1c2128; }
.hot-source { font-size: 0.68em; font-weight: 700; color: var(--text-dim);
              padding: 1px 6px; background: #21262d; border-radius: 8px; }
.hot-date { font-size: 0.68em; color: var(--text-dim); margin-left: 6px; }
.hot-title-en { font-size: 0.82em; color: var(--text-bright); margin-top: 4px; line-height: 1.4; }
.hot-title-zh { font-size: 0.78em; color: var(--text-dim); line-height: 1.4; }
.hot-empty { color: var(--text-dim); font-size: 0.8em; padding: 8px 0; }

@media (max-width: 600px) {
  .card-actions { gap: 6px; }
  .btn { padding: 4px 9px; font-size: 0.74em; }
  .token-input { width: 100%; }
}
"""


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

JS = r"""
// ── GitHub token management ──
function getToken() { return localStorage.getItem('gh_pat') || ''; }
function setToken(t) { localStorage.setItem('gh_pat', t); }

function checkToken() {
  const t = getToken();
  const banner = document.getElementById('token-banner');
  if (banner) banner.style.display = t ? 'none' : 'block';
  // Enable/disable save buttons
  document.querySelectorAll('.btn-save').forEach(b => {
    b.style.opacity = t ? '1' : '0.4';
    b.style.cursor  = t ? 'pointer' : 'not-allowed';
  });
}

function saveToken() {
  const val = document.getElementById('token-input').value.trim();
  if (val) { setToken(val); checkToken(); }
}

// ── Toggle full text panel ──
function togglePaste(cardId) {
  const panel = document.getElementById('ft-' + cardId);
  panel.classList.toggle('open');
}

// ── Update analyze button when text is pasted ──
function onTextChange(cardId) {
  const area = document.getElementById('ta-' + cardId);
  const btn  = document.getElementById('analyze-btn-' + cardId);
  if (area.value.trim().length > 100) {
    btn.classList.add('enabled');
    btn.style.opacity = '1';
    btn.style.cursor  = 'pointer';
  } else {
    btn.classList.remove('enabled');
    btn.style.opacity = '0.4';
    btn.style.cursor  = 'not-allowed';
  }
}

// ── Save full text to GitHub ──
async function saveFullText(cardId, articleMeta) {
  const token = getToken();
  if (!token) { alert('請先設定 GitHub Personal Access Token'); return; }
  const text = document.getElementById('ta-' + cardId).value.trim();
  if (!text) { alert('請先貼上文章全文'); return; }

  const statusEl = document.getElementById('save-status-' + cardId);
  statusEl.textContent = '儲存中...'; statusEl.className = 'save-status';

  const date = new Date().toISOString().slice(0, 10);
  const hash = btoa(articleMeta.url).replace(/[^a-zA-Z0-9]/g, '').slice(0, 12);
  const path = `soc_planning_agent/archive/fulltext/${date}_${hash}.json`;
  const payload = {
    url:       articleMeta.url,
    title_en:  articleMeta.title_en,
    title_zh:  articleMeta.title_zh,
    source:    articleMeta.source,
    date:      articleMeta.date,
    category:  articleMeta.category,
    saved_at:  new Date().toISOString(),
    fulltext:  text,
  };

  try {
    // Check if file exists to get SHA
    let sha = '';
    try {
      const chk = await fetch(
        `https://api.github.com/repos/REPO_PLACEHOLDER/contents/${path}`,
        { headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github.v3+json' }}
      );
      if (chk.ok) { sha = (await chk.json()).sha; }
    } catch {}

    const body = { message: `fulltext: ${articleMeta.title_en.slice(0,60)}`,
                   content: btoa(unescape(encodeURIComponent(JSON.stringify(payload, null, 2)))),
                   branch: 'master' };
    if (sha) body.sha = sha;

    const res = await fetch(
      `https://api.github.com/repos/REPO_PLACEHOLDER/contents/${path}`,
      { method: 'PUT', headers: {
          Authorization: `token ${token}`,
          Accept: 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        }, body: JSON.stringify(body) }
    );
    if (res.ok) {
      statusEl.textContent = '✅ 已儲存到 GitHub'; statusEl.className = 'save-status ok';
    } else {
      const err = await res.json();
      statusEl.textContent = `❌ ${err.message}`; statusEl.className = 'save-status err';
    }
  } catch(e) {
    statusEl.textContent = `❌ ${e.message}`; statusEl.className = 'save-status err';
  }
}

// ── Toggle deep analysis panel ──
function toggleAnalysis(cardId, articleMeta, promptTemplate) {
  const btn = document.getElementById('analyze-btn-' + cardId);
  if (!btn.classList.contains('enabled')) return;
  const panel = document.getElementById('ap-' + cardId);
  if (panel.classList.contains('open')) {
    panel.classList.remove('open'); return;
  }
  // Build prompt
  const fulltext = document.getElementById('ta-' + cardId).value.trim();
  const prompt = promptTemplate
    .replace('{title}',    articleMeta.title_en)
    .replace('{source}',   articleMeta.source)
    .replace('{date}',     articleMeta.date)
    .replace('{fulltext}', fulltext);
  document.getElementById('prompt-' + cardId).textContent = prompt;
  panel.classList.add('open');
}

// ── Copy prompt to clipboard ──
function copyPrompt(cardId) {
  const text = document.getElementById('prompt-' + cardId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copy-btn-' + cardId);
    btn.textContent = '✅ 已複製'; setTimeout(() => btn.textContent = '📋 複製 Prompt', 2000);
  });
}

// ── Bookmark article ──
async function bookmarkArticle(cardId, articleMeta) {
  const token = getToken();
  if (!token) { alert('請先設定 GitHub Personal Access Token'); return; }

  const btn = document.getElementById('bm-btn-' + cardId);
  if (btn.disabled) return;

  const date = new Date().toISOString().slice(0, 10);
  const hash = btoa(articleMeta.url).replace(/[^a-zA-Z0-9]/g, '').slice(0, 12);
  const path = `soc_planning_agent/archive/bookmarks/${date}_${hash}.json`;
  const payload = {
    url:           articleMeta.url,
    title_en:      articleMeta.title_en,
    title_zh:      articleMeta.title_zh,
    source:        articleMeta.source,
    date:          articleMeta.date,
    category:      articleMeta.category,
    bookmarked_at: new Date().toISOString(),
  };

  btn.textContent = '⭐ 儲存中...';

  try {
    // Check if file exists to get SHA
    let sha = '';
    try {
      const chk = await fetch(
        `https://api.github.com/repos/REPO_PLACEHOLDER/contents/${path}`,
        { headers: { Authorization: `token ${token}`, Accept: 'application/vnd.github.v3+json' }}
      );
      if (chk.ok) { sha = (await chk.json()).sha; }
    } catch {}

    const body = {
      message: `bookmark: ${articleMeta.title_en.slice(0, 60)}`,
      content: btoa(unescape(encodeURIComponent(JSON.stringify(payload, null, 2)))),
      branch: 'master',
    };
    if (sha) body.sha = sha;

    const res = await fetch(
      `https://api.github.com/repos/REPO_PLACEHOLDER/contents/${path}`,
      { method: 'PUT', headers: {
          Authorization: `token ${token}`,
          Accept: 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        }, body: JSON.stringify(body) }
    );
    if (res.ok) {
      btn.textContent = '⭐ 已關注';
      btn.style.opacity = '0.6';
      btn.disabled = true;
      btn.classList.add('bookmarked');
      localStorage.setItem('bm_' + cardId, '1');
    } else {
      const err = await res.json();
      btn.textContent = '⭐ 加入關注';
      alert('❌ ' + err.message);
    }
  } catch(e) {
    btn.textContent = '⭐ 加入關注';
    alert('❌ ' + e.message);
  }
}

// ── Restore bookmark state on page load ──
function initBookmarks() {
  document.querySelectorAll('[id^="bm-btn-"]').forEach(btn => {
    const cardId = btn.id.replace('bm-btn-', '');
    if (localStorage.getItem('bm_' + cardId) === '1') {
      btn.textContent = '⭐ 已關注';
      btn.style.opacity = '0.6';
      btn.disabled = true;
      btn.classList.add('bookmarked');
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  checkToken();
  initBookmarks();
});
"""


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _article_card(article: dict, card_id: str, prompt_template_js: str) -> str:
    title_en  = _esc(article.get("title", ""))
    title_zh  = _esc(article.get("title_zh", ""))
    url       = article.get("url", "#")
    source    = _esc(article.get("source", ""))
    pub       = (article.get("published", "") or "")[:10]
    category  = article.get("category", "")
    sum_en    = _esc(article.get("summary", ""))
    sum_zh    = _esc(article.get("summary_zh", ""))
    is_en     = article.get("title_zh", "") != article.get("title", "")

    lang_tag = '<span class="lang-tag">EN→中</span>' if is_en else '<span class="lang-tag">中文</span>'

    # HTML-escape the JSON so double quotes don't break onclick="..." attributes
    meta_js = _esc(json.dumps({
        "url": url, "title_en": article.get("title",""),
        "title_zh": article.get("title_zh",""),
        "source": article.get("source",""),
        "date": pub, "category": category,
    }))

    summary_block = ""
    if sum_en:
        summary_block = f"""
<div class="summary-block">
  <div class="summary-en">{sum_en}</div>
  {f'<div class="summary-zh">{sum_zh}</div>' if sum_zh and sum_zh != sum_en else ""}
</div>"""

    return f"""
<div class="card" id="card-{card_id}">
  <div class="card-head">
    <div class="card-meta-row">
      <span class="source-tag">{source}</span>
      <span class="date-tag">{pub}</span>
      {lang_tag}
    </div>
    <div class="title-en"><a href="{_esc(url)}" target="_blank">{title_en}</a></div>
    {f'<div class="title-zh">{title_zh}</div>' if title_zh and title_zh != title_en else ""}
    {summary_block}
    <div class="card-actions">
      <a class="btn btn-read" href="{_esc(url)}" target="_blank">🔗 閱讀全文</a>
      <button class="btn btn-paste" onclick="togglePaste('{card_id}')">📋 貼上全文</button>
      <button class="btn btn-analyze" id="analyze-btn-{card_id}"
              onclick="toggleAnalysis('{card_id}', {meta_js}, PROMPT_TEMPLATE)">🔬 深度分析</button>
      <button class="btn btn-bookmark" id="bm-btn-{card_id}"
              onclick="bookmarkArticle('{card_id}', {meta_js})">⭐ 加入關注</button>
    </div>
  </div>

  <div class="fulltext-panel" id="ft-{card_id}">
    <div class="panel-label">📄 貼上文章全文（存入 GitHub 備份）</div>
    <textarea class="fulltext-area" id="ta-{card_id}"
              placeholder="請貼上文章全文..."
              oninput="onTextChange('{card_id}')"></textarea>
    <div class="panel-actions">
      <button class="btn btn-save" onclick="saveFullText('{card_id}', {meta_js})">💾 儲存全文</button>
      <span class="save-status" id="save-status-{card_id}"></span>
    </div>
  </div>

  <div class="analysis-panel" id="ap-{card_id}">
    <div class="panel-label">🔬 深度分析 Prompt（複製後貼到 Claude.ai）</div>
    <div class="prompt-box" id="prompt-{card_id}"></div>
    <div class="panel-actions">
      <button class="btn btn-copy-prompt" id="copy-btn-{card_id}"
              onclick="copyPrompt('{card_id}')">📋 複製 Prompt</button>
      <a class="btn btn-read" href="https://claude.ai" target="_blank">開啟 Claude.ai →</a>
    </div>
  </div>
</div>"""


def _collection_page(category: str, articles: list, date: str) -> str:
    emoji, label = CATEGORY_LABEL.get(category, ("📰", category.upper()))
    prompt_js = json.dumps(ANALYSIS_PROMPT_TEMPLATE)
    cards = "\n".join(_article_card(a, f"{category[:3]}{i}", prompt_js)
                      for i, a in enumerate(articles))

    token_banner = f"""
<div class="token-banner" id="token-banner">
  <strong>⚙️ 設定 GitHub Token</strong>（用於儲存全文到 GitHub）<br>
  <small>需要 <code>repo</code> 權限的 Personal Access Token，只需設定一次。</small><br>
  <input class="token-input" id="token-input" type="password" placeholder="ghp_xxxxxxxxxxxx"><br>
  <button class="btn btn-save" onclick="saveToken()" style="margin-top:6px">儲存 Token</button>
</div>"""

    now_tw = datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M')
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{emoji} {label} — {date}</title>
<style>{CSS}</style>
</head>
<body>
<a class="back" href="index.html">← 返回總覽</a>
<h1>{emoji} {label}</h1>
<div class="page-meta">{date} &nbsp;·&nbsp; {len(articles)} 篇 &nbsp;·&nbsp; 更新：{now_tw} (台灣時間)</div>
{token_banner}
<script>const PROMPT_TEMPLATE = {prompt_js};</script>
{cards}
<script>{JS.replace('REPO_PLACEHOLDER', GITHUB_REPO)}</script>
</body></html>"""


def _hot_section_html(icon: str, title: str, articles: list) -> str:
    """Render a hot-section block (🔥 重大消息 or ⭐ 我的關注)."""
    count = len(articles)
    if articles:
        cards_html = ""
        for a in articles:
            url      = _esc(a.get("url", "#"))
            source   = _esc(a.get("source", ""))
            date     = _esc((a.get("date", "") or a.get("published", "") or "")[:10])
            title_en = _esc(a.get("title", "") or a.get("title_en", ""))
            title_zh = _esc(a.get("title_zh", ""))
            cards_html += f"""<a class="hot-card" href="{url}" target="_blank">
  <span class="hot-source">{source}</span><span class="hot-date">{date}</span>
  <div class="hot-title-en">{title_en}</div>
  {f'<div class="hot-title-zh">{title_zh}</div>' if title_zh else ""}
</a>
"""
    else:
        cards_html = '<div class="hot-empty">尚無資料</div>'

    return f"""<div class="hot-section">
  <div class="hot-header">
    <span class="hot-icon">{icon}</span>
    <h2>{title}</h2>
    <span class="hot-count">{count} 篇</span>
  </div>
  {cards_html}
</div>"""


def _index_page(reports: list, hot_articles: list = None, interest_articles: list = None) -> str:
    if hot_articles is None:
        hot_articles = []
    if interest_articles is None:
        interest_articles = []

    # Hot News section
    hot_section = _hot_section_html("🔥", "重大消息", hot_articles)
    interest_section = (
        '<div class="hot-section" style="margin-top:16px">\n'
        + _hot_section_html("⭐", "我的關注", interest_articles)[len('<div class="hot-section">\n'):]
    )

    # Report cards
    cards = ""
    for r in sorted(reports, key=lambda x: x["date"], reverse=True):
        emoji, label = CATEGORY_LABEL.get(r["category"], ("📰", r["category"]))
        cards += f"""
<a class="index-card" href="{_esc(r['filename'])}">
  <h2>{emoji} {label} — {r['date']}</h2>
  <div class="card-meta">
    {r['total']} 篇 &nbsp;·&nbsp;
    <span class="new-count">+{r.get('new',r['total'])} 新</span>
  </div>
</a>"""

    now_tw = datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M')
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SOC Planning Agent — Reports</title>
<style>{CSS}</style>
</head>
<body>
<h1>📊 SOC Planning Agent</h1>
<div class="page-meta">最後更新：{now_tw} (台灣時間) &nbsp;·&nbsp; 每 2 小時自動更新</div>
<br>
{hot_section}
{interest_section}
<br>
{cards if cards else '<div class="page-meta">尚無報告，等待 RSS 收集中...</div>'}
</body></html>"""


# ---------------------------------------------------------------------------
# Entry point called by github_collector.py
# ---------------------------------------------------------------------------

def generate_reports(articles_by_category: dict, date: str) -> list:
    """Write collection HTML pages + update index. Returns list of report info dicts."""
    DOCS_DIR.mkdir(exist_ok=True)

    # Find next collection ID
    existing_ids = []
    for f in DOCS_DIR.glob("collection_*.html"):
        parts = f.stem.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            existing_ids.append(int(parts[1]))
    next_id = max(existing_ids, default=0) + 1

    # Compute hot news from all articles in this run
    all_articles_flat = []
    for articles in articles_by_category.values():
        all_articles_flat.extend(articles)
    scored = sorted(
        all_articles_flat,
        key=_importance_score,
        reverse=True,
    )
    hot_articles = [a for a in scored if _importance_score(a) >= 3][:8]

    # Load user interest articles (bookmarks + fulltext)
    interest_articles = _load_user_interest()

    new_reports = []
    for i, (category, articles) in enumerate(articles_by_category.items()):
        if not articles:
            continue
        coll_id  = next_id + i
        html     = _collection_page(category, articles, date)
        fname    = f"collection_{coll_id}_{category}_{date}.html"
        (DOCS_DIR / fname).write_text(html, encoding="utf-8")
        print(f"  ✓ {fname} ({len(articles)} articles)")
        new_reports.append({
            "filename": fname, "category": category,
            "date": date, "total": len(articles), "new": len(articles),
        })

    # Rebuild index — merge new + all existing
    fresh = {r["filename"] for r in new_reports}
    existing_reports = []
    for f in sorted(DOCS_DIR.glob("collection_*.html"), reverse=True):
        if f.name in fresh:
            continue
        parts = f.stem.split("_")
        if len(parts) >= 4:
            existing_reports.append({
                "filename": f.name,
                "category": "_".join(parts[2:-1]),
                "date": parts[-1],
                "total": "?", "new": 0,
            })

    all_reports = new_reports + existing_reports
    (DOCS_DIR / "index.html").write_text(
        _index_page(all_reports, hot_articles=hot_articles, interest_articles=interest_articles),
        encoding="utf-8",
    )
    print(f"  ✓ index.html ({len(all_reports)} reports)")

    # Write output vars for GitHub Actions
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"new_reports={len(new_reports)}\n")
            f.write(f"pages_url={PAGES_URL}\n")

    return new_reports


# ---------------------------------------------------------------------------
# Rebuild all pages from archive (run after code changes to fix existing pages)
# ---------------------------------------------------------------------------

def rebuild_from_archive():
    """Re-generate all collection HTML pages from archive/rss/*.json data."""
    ARCHIVE_RSS_DIR = ROOT / "archive" / "rss"
    if not ARCHIVE_RSS_DIR.exists():
        print("No archive data found.")
        return

    DOCS_DIR.mkdir(exist_ok=True)
    for f in DOCS_DIR.glob("collection_*.html"):
        f.unlink()

    all_reports, coll_id = [], 1
    latest_articles = []   # only most-recent day → hot news

    archive_files = sorted(ARCHIVE_RSS_DIR.glob("*.json"))
    for idx, archive_file in enumerate(archive_files):
        is_latest = (idx == len(archive_files) - 1)
        try:
            data     = json.loads(archive_file.read_text(encoding="utf-8"))
            date_str = data.get("date", archive_file.stem)
            articles = data.get("articles", [])
        except Exception as e:
            print(f"  ⚠ skip {archive_file.name}: {e}"); continue

        by_cat: dict = {}
        for a in articles:
            by_cat.setdefault(a.get("category", "unknown"), []).append(a)

        for cat, arts in by_cat.items():
            fname = f"collection_{coll_id}_{cat}_{date_str}.html"
            (DOCS_DIR / fname).write_text(_collection_page(cat, arts, date_str), encoding="utf-8")
            print(f"  ✓ {fname} ({len(arts)} articles)")
            all_reports.append({"filename": fname, "category": cat,
                                 "date": date_str, "total": len(arts), "new": 0})
            if is_latest:
                latest_articles.extend(arts)
            coll_id += 1

    interest = _load_user_interest()
    hot = [a for a in sorted(latest_articles, key=_importance_score, reverse=True)
           if _importance_score(a) >= 3][:8]
    (DOCS_DIR / "index.html").write_text(
        _index_page(all_reports, hot_articles=hot, interest_articles=interest), encoding="utf-8"
    )
    print(f"\n✅ Rebuilt {len(all_reports)} pages + index.html")


if __name__ == "__main__":
    import sys
    if "--rebuild" in sys.argv:
        print("🔨 Rebuilding all HTML from archive data...")
        rebuild_from_archive()
    else:
        print("Usage: python generate_html.py --rebuild")
