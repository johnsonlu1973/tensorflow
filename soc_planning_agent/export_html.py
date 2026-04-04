"""HTML report generator for SOC Planning Agent collections.

Generates a dark-themed, mobile-friendly HTML report with:
- Overview table (article num, type badge, title, one-liner)
- Expandable panels for trend articles: original text + deep analysis
- Clickable links to original articles
"""
import json
import re
from datetime import datetime
from pathlib import Path

CATEGORY_EMOJI = {
    "agentic_ai": "🤖",
    "chips_soc":  "💾",
    "mobile":     "📱",
    "5g_cpe":     "📡",
    "csp_cloud":  "☁️",
    "3gpp":       "📋",
}

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0f1117; color: #e0e0e0;
  padding: 16px; max-width: 900px; margin: 0 auto;
}
h1 { color: #58a6ff; font-size: 1.25em; padding-bottom: 10px;
     border-bottom: 1px solid #30363d; margin-bottom: 6px; }
.meta { color: #8b949e; font-size: 0.82em; margin-bottom: 20px; }
.back { color: #58a6ff; text-decoration: none; font-size: 0.85em; display: inline-block; margin-bottom: 14px; }
.back:hover { text-decoration: underline; }

/* Overview table */
table { width: 100%; border-collapse: collapse; }
th {
  background: #161b22; color: #8b949e; text-align: left;
  padding: 9px 10px; font-size: 0.75em; text-transform: uppercase;
  letter-spacing: 0.05em; border-bottom: 1px solid #30363d;
}
td { padding: 9px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }
tr:hover td { background: #161b22; }
.num { color: #8b949e; width: 28px; font-size: 0.85em; }
.badge-trend {
  background: #1a4731; color: #3fb950;
  padding: 2px 8px; border-radius: 12px; font-size: 0.72em; font-weight: 600;
  white-space: nowrap;
}
.badge-info {
  background: #21262d; color: #8b949e;
  padding: 2px 8px; border-radius: 12px; font-size: 0.72em;
  white-space: nowrap;
}
.title-link { color: #e0e0e0; text-decoration: none; font-size: 0.88em; line-height: 1.4; }
.title-link:hover { color: #58a6ff; text-decoration: underline; }
.source-tag { color: #8b949e; font-size: 0.73em; margin-top: 2px; }
.one-liner { color: #8b949e; font-size: 0.83em; line-height: 1.5; }

/* Expand button */
.toggle-btn {
  display: inline-block; margin-top: 6px;
  background: #1a4731; color: #3fb950;
  border: none; padding: 3px 10px; border-radius: 6px;
  cursor: pointer; font-size: 0.75em; font-weight: 600;
}
.toggle-btn.info-btn { background: #21262d; color: #8b949e; }
.toggle-btn:hover { opacity: 0.8; }

/* Detail panel */
.detail-row td { padding: 0 10px 12px; }
.detail { display: none; background: #161b22; border: 1px solid #30363d;
          border-radius: 8px; overflow: hidden; }
.detail.open { display: block; }
.detail-section { padding: 14px 16px; }
.detail-section + .detail-section { border-top: 1px solid #30363d; }
.section-title { color: #e3b341; font-size: 0.78em; font-weight: 700;
                 text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
.excerpt {
  font-size: 0.82em; line-height: 1.7; color: #c9d1d9;
  white-space: pre-wrap; word-break: break-word;
}
.analysis { font-size: 0.84em; line-height: 1.75; color: #c9d1d9; }
.analysis h2 {
  color: #58a6ff; font-size: 0.88em; margin: 14px 0 4px;
  padding-bottom: 3px; border-bottom: 1px solid #30363d;
}
.analysis table { margin: 8px 0; }
.analysis th { font-size: 0.8em; padding: 6px 8px; }
.analysis td { font-size: 0.8em; padding: 6px 8px; color: #c9d1d9; }
.orig-link {
  display: inline-block; margin-top: 10px;
  color: #58a6ff; font-size: 0.8em; text-decoration: none;
}
.orig-link:hover { text-decoration: underline; }

/* Index page */
.card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 14px 16px; margin-bottom: 10px; text-decoration: none;
  display: block; transition: border-color 0.15s;
}
.card:hover { border-color: #58a6ff; }
.card h2 { color: #58a6ff; font-size: 1em; margin-bottom: 4px; }
.card .card-meta { color: #8b949e; font-size: 0.8em; }
.card .trend-count { color: #3fb950; font-weight: 600; }

@media (max-width: 600px) {
  body { padding: 10px; }
  th, td { padding: 8px 6px; }
  .one-liner { display: none; }
}
"""

JS = """
function toggle(id) {
  var d = document.getElementById('detail-' + id);
  var btn = document.getElementById('btn-' + id);
  if (d.classList.contains('open')) {
    d.classList.remove('open');
    btn.textContent = btn.textContent.replace('▼', '▶');
  } else {
    d.classList.add('open');
    btn.textContent = btn.textContent.replace('▶', '▼');
  }
}
"""


def _md_to_html(text: str) -> str:
    """Minimal markdown → HTML conversion for analysis text."""
    # Headers
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Bullet lists
    text = re.sub(r'^\s*[•·\-\*] (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*?</li>\n?)+', lambda m: '<ul>' + m.group(0) + '</ul>', text, flags=re.DOTALL)
    # Line breaks
    text = text.replace('\n\n', '<br><br>')
    return text


def generate_collection_html(item: dict, articles: list) -> str:
    category = item.get("category", "")
    emoji = CATEGORY_EMOJI.get(category, "📰")
    topic = item.get("topic", "")
    date = item.get("collected_at", "")[:10]
    n_trend = sum(1 for a in articles if a.get("article_type") == "trend")

    rows = ""
    for i, a in enumerate(articles, 1):
        atype = a.get("article_type", "info")
        is_trend = atype == "trend"
        url = a.get("url", "")
        title = a.get("title", "")
        source = a.get("source", "")
        one_liner = a.get("one_liner", "") or "—"

        badge = (
            '<span class="badge-trend">趨勢</span>' if is_trend
            else '<span class="badge-info">資訊</span>'
        )
        title_html = (
            f'<a class="title-link" href="{url}" target="_blank">{title}</a>'
            if url else f'<span class="title-link">{title}</span>'
        )

        btn_html = ""
        detail_html = ""

        full_text = (a.get("full_text") or a.get("rss_summary", ""))[:1500]
        analysis_raw = a.get("analysis", "").strip()

        if is_trend and analysis_raw:
            btn_html = f'<br><button class="toggle-btn" id="btn-{i}" onclick="toggle({i})">▶ 深度分析</button>'
            excerpt_html = full_text.replace("<", "&lt;").replace(">", "&gt;")
            analysis_html = _md_to_html(analysis_raw)
            orig_link = f'<a class="orig-link" href="{url}" target="_blank">🔗 開啟原文</a>' if url else ""
            detail_html = f"""
<tr class="detail-row"><td colspan="4">
  <div class="detail" id="detail-{i}">
    <div class="detail-section">
      <div class="section-title">📄 原文摘錄</div>
      <div class="excerpt">{excerpt_html}</div>
      {orig_link}
    </div>
    <div class="detail-section">
      <div class="section-title">🔬 深度分析</div>
      <div class="analysis">{analysis_html}</div>
    </div>
  </div>
</td></tr>"""

        elif not is_trend:
            rss = (a.get("rss_summary", "") or "")[:400]
            if rss:
                btn_html = f'<br><button class="toggle-btn info-btn" id="btn-{i}" onclick="toggle({i})">▶ RSS 摘要</button>'
                rss_escaped = rss.replace("<", "&lt;").replace(">", "&gt;")
                detail_html = f"""
<tr class="detail-row"><td colspan="4">
  <div class="detail" id="detail-{i}">
    <div class="detail-section">
      <div class="excerpt">{rss_escaped}</div>
    </div>
  </div>
</td></tr>"""

        rows += f"""<tr>
  <td class="num">{i}</td>
  <td>{badge}</td>
  <td>{title_html}<div class="source-tag">{source}</div>{btn_html}</td>
  <td class="one-liner">{one_liner}</td>
</tr>{detail_html}"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{emoji} {category.upper()} — {date}</title>
<style>{CSS}</style>
</head>
<body>
<a class="back" href="index.html">← 返回總覽</a>
<h1>{emoji} {topic}</h1>
<div class="meta">{date} &nbsp;|&nbsp; {len(articles)} 篇 &nbsp;|&nbsp; <span style="color:#3fb950">{n_trend} 趨勢類</span></div>
<table>
  <thead><tr><th>#</th><th>類型</th><th>標題</th><th>一句話</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<script>{JS}</script>
</body></html>"""


def generate_index_html(collections_info: list) -> str:
    """Generate index page listing all available collection reports."""
    cards = ""
    for info in sorted(collections_info, key=lambda x: x["date"], reverse=True):
        emoji = CATEGORY_EMOJI.get(info["category"], "📰")
        cards += f"""
<a class="card" href="{info['filename']}">
  <h2>{emoji} {info['category'].upper()} — {info['date']}</h2>
  <div class="card-meta">
    {info['total']} 篇 &nbsp;|&nbsp;
    <span class="trend-count">{info['trend']} 趨勢類</span>
  </div>
</a>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SOC Planning Agent — Reports</title>
<style>{CSS}</style>
</head>
<body>
<h1>📊 SOC Planning Agent — News Reports</h1>
<div class="meta">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<br>
{cards}
</body></html>"""
