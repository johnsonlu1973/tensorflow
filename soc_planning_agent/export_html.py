"""HTML report generator for SOC Planning Agent collections."""
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
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0d1117; color: #c9d1d9;
  padding: 16px 12px; max-width: 860px; margin: 0 auto; line-height: 1.6;
}

/* ── Nav ── */
.back { color: #58a6ff; text-decoration: none; font-size: 0.82em;
        display: inline-block; margin-bottom: 14px; }
.back:hover { text-decoration: underline; }

/* ── Page header ── */
h1 { color: #58a6ff; font-size: 1.2em; margin-bottom: 4px; }
.page-meta { color: #8b949e; font-size: 0.8em; margin-bottom: 20px; }
.trend-pill { color: #3fb950; font-weight: 600; }

/* ── Article card ── */
.article {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  margin-bottom: 10px; overflow: hidden;
}
.article-header {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 12px 14px; cursor: pointer; user-select: none;
}
.article-header:hover { background: #1c2128; }
.art-num { color: #8b949e; font-size: 0.8em; min-width: 22px; padding-top: 2px; }
.badge {
  padding: 2px 9px; border-radius: 12px; font-size: 0.7em;
  font-weight: 700; white-space: nowrap; flex-shrink: 0; margin-top: 2px;
}
.badge-trend { background: #1a4731; color: #3fb950; }
.badge-info  { background: #21262d; color: #8b949e; }
.art-right { flex: 1; min-width: 0; }
.art-title { color: #e6edf3; font-size: 0.9em; font-weight: 600;
             line-height: 1.4; margin-bottom: 3px; }
.art-title a { color: inherit; text-decoration: none; }
.art-title a:hover { color: #58a6ff; }
.art-meta { color: #8b949e; font-size: 0.75em; margin-bottom: 5px; }
.art-summary { color: #8b949e; font-size: 0.82em; line-height: 1.5; }
.expand-icon { color: #8b949e; font-size: 0.8em; flex-shrink: 0; padding-top: 2px; }

/* ── Detail panel ── */
.article-detail { display: none; border-top: 1px solid #30363d; }
.article-detail.open { display: block; }

.detail-block { padding: 14px 16px; }
.detail-block + .detail-block { border-top: 1px solid #21262d; }
.block-label {
  font-size: 0.7em; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; margin-bottom: 8px;
}
.label-excerpt  { color: #e3b341; }
.label-analysis { color: #58a6ff; }

.excerpt-text {
  font-size: 0.82em; line-height: 1.7; color: #b0bac5;
  white-space: pre-wrap; word-break: break-word;
}
.orig-link {
  display: inline-block; margin-top: 8px; font-size: 0.78em;
  color: #58a6ff; text-decoration: none;
}
.orig-link:hover { text-decoration: underline; }

/* ── Analysis sections ── */
.analysis-body { font-size: 0.84em; color: #c9d1d9; }

.ana-section { margin-bottom: 18px; }
.ana-section:last-child { margin-bottom: 0; }
.ana-title {
  color: #58a6ff; font-size: 0.85em; font-weight: 700;
  border-bottom: 1px solid #21262d; padding-bottom: 4px; margin-bottom: 8px;
}

/* Tables inside analysis */
.ana-table { width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 0.9em; }
.ana-table th {
  background: #1c2128; color: #8b949e; text-align: left;
  padding: 6px 10px; font-weight: 600; font-size: 0.85em;
  border: 1px solid #30363d;
}
.ana-table td {
  padding: 6px 10px; border: 1px solid #21262d;
  vertical-align: top; line-height: 1.5;
}
.ana-table tr:nth-child(even) td { background: #1c2128; }

/* Lists inside analysis */
.ana-ul { padding-left: 16px; margin: 4px 0; }
.ana-ul li { margin-bottom: 3px; line-height: 1.5; }
.ana-ul li::marker { color: #58a6ff; }

/* ── Index page ── */
.index-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 14px 16px; margin-bottom: 10px; text-decoration: none; display: block;
  transition: border-color 0.15s, background 0.15s;
}
.index-card:hover { border-color: #58a6ff; background: #1c2128; }
.index-card h2 { color: #58a6ff; font-size: 0.95em; margin-bottom: 4px; }
.index-card .card-meta { color: #8b949e; font-size: 0.8em; }
.trend-count { color: #3fb950; font-weight: 600; }

@media (max-width: 600px) {
  h1 { font-size: 1.05em; }
  .art-title { font-size: 0.85em; }
  .detail-block { padding: 10px 12px; }
}
"""

JS = """
function toggleArticle(id) {
  var detail = document.getElementById('d' + id);
  var icon   = document.getElementById('i' + id);
  if (detail.classList.contains('open')) {
    detail.classList.remove('open');
    icon.textContent = '▶';
  } else {
    detail.classList.add('open');
    icon.textContent = '▼';
  }
}
"""


# ---------------------------------------------------------------------------
# Markdown → HTML (minimal, focused on analysis output format)
# ---------------------------------------------------------------------------

def _md_to_analysis_html(text: str) -> str:
    """Convert analysis markdown to clean HTML with section cards."""
    sections = re.split(r'^## ', text, flags=re.MULTILINE)
    html_parts = []
    for sec in sections:
        if not sec.strip():
            continue
        lines = sec.strip().split('\n', 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        body_html = _render_body(body)
        html_parts.append(
            f'<div class="ana-section">'
            f'<div class="ana-title">{title}</div>'
            f'<div>{body_html}</div>'
            f'</div>'
        )
    return '<div class="analysis-body">' + ''.join(html_parts) + '</div>'


def _render_body(text: str) -> str:
    """Render section body: detect tables, bullet lists, and plain paragraphs."""
    blocks = []
    current = []

    def flush():
        if current:
            blocks.append(('para', '\n'.join(current)))
            current.clear()

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Table detection: line starts with |
        if line.strip().startswith('|'):
            flush()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            blocks.append(('table', table_lines))
            continue
        # Bullet list
        if re.match(r'^\s*[-•·*]\s', line) or re.match(r'^\s{2,}[-•·*]\s', line):
            flush()
            items = []
            while i < len(lines) and (re.match(r'^\s*[-•·*]\s', lines[i]) or re.match(r'^\s{2,}[-•·*]\s', lines[i])):
                items.append(re.sub(r'^\s*[-•·*]\s*', '', lines[i]))
                i += 1
            blocks.append(('ul', items))
            continue
        current.append(line)
        i += 1
    flush()

    result = []
    for kind, data in blocks:
        if kind == 'table':
            result.append(_render_table(data))
        elif kind == 'ul':
            items_html = ''.join(f'<li>{_inline(item)}</li>' for item in data if item.strip())
            result.append(f'<ul class="ana-ul">{items_html}</ul>')
        else:
            para = _inline(data.strip())
            if para:
                result.append(f'<p style="margin:4px 0 8px">{para}</p>')
    return ''.join(result)


def _render_table(lines: list) -> str:
    """Render markdown table to HTML."""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    if not rows:
        return ""
    # Second row is usually separator (---|---), skip it
    data_rows = [r for r in rows if not all(re.match(r'^[-:\s]+$', c) for c in r)]
    if not data_rows:
        return ""
    header = data_rows[0]
    body_rows = data_rows[1:]
    th = ''.join(f'<th>{_inline(c)}</th>' for c in header)
    trs = ''
    for row in body_rows:
        tds = ''.join(f'<td>{_inline(c)}</td>' for c in row)
        trs += f'<tr>{tds}</tr>'
    return f'<table class="ana-table"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def _inline(text: str) -> str:
    """Inline markdown: bold, code."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


# ---------------------------------------------------------------------------
# Collection HTML generator
# ---------------------------------------------------------------------------

def generate_collection_html(item: dict, articles: list) -> str:
    category = item.get("category", "")
    emoji = CATEGORY_EMOJI.get(category, "📰")
    topic = item.get("topic", "")
    date = item.get("collected_at", "")[:10]
    n_trend = sum(1 for a in articles if a.get("article_type") == "trend")

    cards_html = ""
    for i, a in enumerate(articles, 1):
        atype = a.get("article_type", "info")
        is_trend = atype == "trend"
        url = a.get("url", "") or ""
        title = a.get("title", "")
        source = a.get("source", "")
        published = a.get("published", "")[:16]
        one_liner = a.get("one_liner", "") or ""
        rss_summary = (a.get("rss_summary") or a.get("summary") or "").strip()
        full_text = (a.get("full_text") or "").strip()
        analysis_raw = (a.get("analysis") or "").strip()

        badge_cls = "badge-trend" if is_trend else "badge-info"
        badge_txt = "趨勢" if is_trend else "資訊"
        title_html = (f'<a href="{url}" target="_blank">{title}</a>'
                      if url else title)

        # Summary text to show (full_text if available, else rss_summary)
        display_summary = full_text if (full_text and len(full_text) > len(rss_summary)) else rss_summary
        summary_escaped = display_summary[:2000].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        has_detail = bool(display_summary or analysis_raw)
        expand_icon = f'<span class="expand-icon" id="i{i}">▶</span>' if has_detail else ''
        header_onclick = f' onclick="toggleArticle({i})"' if has_detail else ''

        # Build detail panel
        detail_inner = ""
        if display_summary:
            orig_link = f'<a class="orig-link" href="{url}" target="_blank">🔗 開啟原文 →</a>' if url else ""
            detail_inner += f"""
<div class="detail-block">
  <div class="block-label label-excerpt">📄 原文摘錄</div>
  <div class="excerpt-text">{summary_escaped}</div>
  {orig_link}
</div>"""

        if analysis_raw:
            analysis_html = _md_to_analysis_html(analysis_raw)
            detail_inner += f"""
<div class="detail-block">
  <div class="block-label label-analysis">🔬 深度分析</div>
  {analysis_html}
</div>"""

        detail_panel = ""
        if has_detail:
            detail_panel = f'<div class="article-detail" id="d{i}">{detail_inner}</div>'

        cards_html += f"""
<div class="article">
  <div class="article-header"{header_onclick}>
    <span class="art-num">{i}</span>
    <span class="badge {badge_cls}">{badge_txt}</span>
    <div class="art-right">
      <div class="art-title">{title_html}</div>
      <div class="art-meta">{source}{'&nbsp;·&nbsp;' + published if published else ''}</div>
      {f'<div class="art-summary">{one_liner}</div>' if one_liner else ''}
    </div>
    {expand_icon}
  </div>
  {detail_panel}
</div>"""

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
<div class="page-meta">{date} &nbsp;·&nbsp; {len(articles)} 篇 &nbsp;·&nbsp;
  <span class="trend-pill">{n_trend} 趨勢類</span>
  &nbsp;·&nbsp; 點擊文章展開詳情
</div>
{cards_html}
<script>{JS}</script>
</body></html>"""


# ---------------------------------------------------------------------------
# Index page generator
# ---------------------------------------------------------------------------

def generate_index_html(collections_info: list) -> str:
    cards = ""
    for info in sorted(collections_info, key=lambda x: (x["date"], x.get("category","")), reverse=True):
        emoji = CATEGORY_EMOJI.get(info["category"], "📰")
        total = info.get("total", "—")
        trend = info.get("trend", "—")
        cards += f"""
<a class="index-card" href="{info['filename']}">
  <h2>{emoji} {info['category'].upper()} — {info['date']}</h2>
  <div class="card-meta">
    {total} 篇 &nbsp;·&nbsp; <span class="trend-count">{trend} 趨勢類</span>
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
<h1>📊 SOC Planning Agent</h1>
<div class="page-meta">最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<br>
{cards}
</body></html>"""
