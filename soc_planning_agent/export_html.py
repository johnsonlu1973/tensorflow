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

/* ── 4-layer flow header ── */
.layer-flow {
  display: flex; align-items: center; gap: 0;
  margin: 12px 0 16px; flex-wrap: wrap;
}
.layer-chip {
  padding: 4px 10px; border-radius: 4px; font-size: 0.72em; font-weight: 700;
  white-space: nowrap;
}
.layer-arrow { color: #8b949e; padding: 0 4px; font-size: 0.9em; }
.layer-1 { background: #1a3a5c; color: #79c0ff; }
.layer-2 { background: #3d2b00; color: #e3b341; }
.layer-3 { background: #1a4731; color: #3fb950; }
.layer-4 { background: #3d1f1f; color: #f85149; }

/* ── Layer section cards ── */
.layer-section {
  border-radius: 6px; margin-bottom: 12px; overflow: hidden;
  border-left: 3px solid;
}
.layer-section-1 { border-color: #388bfd; background: #0d1926; }
.layer-section-2 { border-color: #e3b341; background: #1a1300; }
.layer-section-3 { border-color: #3fb950; background: #0d1a12; }
.layer-section-4 { border-color: #f85149; background: #1a0d0d; }
.layer-section-title {
  padding: 7px 12px; font-size: 0.78em; font-weight: 700;
}
.layer-section-1 .layer-section-title { color: #79c0ff; }
.layer-section-2 .layer-section-title { color: #e3b341; }
.layer-section-3 .layer-section-title { color: #3fb950; }
.layer-section-4 .layer-section-title { color: #f85149; }
.layer-section-body { padding: 10px 14px; }

/* ── Per-audience card (kept for fallback) ── */
.audience-card {
  border: 1px solid #30363d; border-radius: 6px;
  margin-bottom: 12px; overflow: hidden;
}
.audience-header {
  background: #1c2128; padding: 8px 12px;
  font-size: 0.85em; font-weight: 700; color: #e6edf3;
}
.audience-body { padding: 10px 12px; }
.audience-row { display: flex; gap: 8px; margin-bottom: 8px; }
.audience-row:last-child { margin-bottom: 0; }
.row-label {
  font-size: 0.72em; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; color: #8b949e; min-width: 56px;
  padding-top: 2px; flex-shrink: 0;
}
.row-content { font-size: 0.83em; line-height: 1.6; color: #c9d1d9; flex: 1; }

/* ── Industry diagram ── */
.industry-diagram {
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
  padding: 14px 16px; margin: 8px 0;
  font-family: "SF Mono", "Fira Code", "Consolas", monospace;
  font-size: 0.82em; line-height: 1.8; color: #8b949e;
  white-space: pre; overflow-x: auto;
}
.industry-diagram .node { color: #e6edf3; font-weight: 600; }
.industry-diagram .arrow { color: #58a6ff; }

/* Incentive table emphasis */
.incentive-high { color: #f85149; font-weight: 600; }
.incentive-mid  { color: #e3b341; font-weight: 600; }
.incentive-low  { color: #3fb950; }
.attitude-pos   { color: #3fb950; }
.attitude-watch { color: #e3b341; }
.attitude-neg   { color: #f85149; }

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

LAYER_META = {
    '啟動層': ('layer-section-1', '🔵 啟動層：趨勢 → 市場新機會', 1),
    '鎖定層': ('layer-section-2', '🟡 鎖定層：機會 → 目標客群與痛點', 2),
    '轉換層': ('layer-section-3', '🟢 轉換層：痛點 → 客戶價值', 3),
    '收成層': ('layer-section-4', '🔴 收成層：客戶價值 → 商業價值', 4),
}

LAYER_FLOW_HTML = """
<div class="layer-flow">
  <span class="layer-chip layer-1">🔵 趨勢</span>
  <span class="layer-arrow">→</span>
  <span class="layer-chip layer-1">機會</span>
  <span class="layer-arrow">→</span>
  <span class="layer-chip layer-2">🟡 痛點</span>
  <span class="layer-arrow">→</span>
  <span class="layer-chip layer-3">🟢 客戶價值</span>
  <span class="layer-arrow">→</span>
  <span class="layer-chip layer-4">🔴 商業價值</span>
</div>
"""

def _md_to_analysis_html(text: str) -> str:
    """Convert analysis markdown to structured HTML.

    New 4-layer framework:
      ## 啟動層  → blue layer card
      ## 鎖定層  → yellow layer card
      ## 轉換層  → green layer card
      ## 收成層  → red layer card
      ## 產業鏈結構圖  → ASCII diagram
      ## 產業鏈誘因分析 → incentive table

    Legacy sections still supported as fallback.
    """
    sections = re.split(r'^## ', text, flags=re.MULTILINE)
    html_parts = ['<div class="analysis-body">']

    # Detect if this uses the new 4-layer framework
    is_new_framework = any('啟動層' in s or '鎖定層' in s for s in sections)
    if is_new_framework:
        html_parts.append(LAYER_FLOW_HTML)

    for sec in sections:
        if not sec.strip():
            continue
        lines = sec.strip().split('\n', 1)
        title = lines[0].strip()
        body  = lines[1].strip() if len(lines) > 1 else ""

        # Match layer sections
        matched_layer = None
        for key, (css_cls, display_title, _) in LAYER_META.items():
            if key in title:
                matched_layer = (css_cls, display_title)
                break

        if matched_layer:
            css_cls, display_title = matched_layer
            body_html = _render_layer_body(body)
            html_parts.append(
                f'<div class="layer-section {css_cls}">'
                f'<div class="layer-section-title">{display_title}</div>'
                f'<div class="layer-section-body">{body_html}</div>'
                f'</div>'
            )
        elif '結構圖' in title:
            html_parts.append(f'<div class="ana-section"><div class="ana-title">🗺 {title}</div>')
            html_parts.append(_render_diagram(body))
            html_parts.append('</div>')
        elif '誘因' in title:
            html_parts.append(f'<div class="ana-section"><div class="ana-title">⛓ {title}</div>')
            html_parts.append(_render_incentive_section(body))
            html_parts.append('</div>')
        elif '逐一分析' in title:
            html_parts.append(f'<div class="ana-section"><div class="ana-title">{title}</div>')
            html_parts.append(_render_audience_cards(body))
            html_parts.append('</div>')
        else:
            html_parts.append(f'<div class="ana-section"><div class="ana-title">{title}</div>')
            html_parts.append(_render_body(body))
            html_parts.append('</div>')

    html_parts.append('</div>')
    return ''.join(html_parts)


def _render_layer_body(text: str) -> str:
    """Render a layer body: **Label**：content pairs as labelled rows."""
    # Split on **bold label**: pattern
    parts = re.split(r'\*\*(.+?)\*\*[：:]', text)
    if len(parts) < 3:
        return _render_body(text)

    rows_html = ""
    # parts = [pre_text, label1, content1, label2, content2, ...]
    i = 1
    while i + 1 < len(parts):
        label   = parts[i].strip().lstrip('⚠️').strip()
        content = parts[i + 1].strip()
        # Skip rule annotations (lines starting with ⚠️ or -)
        if label.startswith('⚠') or label == '':
            i += 2
            continue
        content_html = _render_body(content)
        rows_html += (
            f'<div class="audience-row">'
            f'<div class="row-label" style="min-width:72px">{label}</div>'
            f'<div class="row-content">{content_html}</div>'
            f'</div>'
        )
        i += 2

    return rows_html if rows_html else _render_body(text)


def _render_audience_cards(text: str) -> str:
    """Render ### sub-sections as per-audience cards with pain/value/biz rows."""
    chunks = re.split(r'^### ', text, flags=re.MULTILINE)
    html = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        lines = chunk.strip().split('\n', 1)
        header = lines[0].strip().lstrip('🎯').strip()
        body   = lines[1].strip() if len(lines) > 1 else ""

        rows_html = ""
        # Parse **Label**：content pairs
        # Also handle separator lines (---)
        body = re.sub(r'^[-─]+$', '', body, flags=re.MULTILINE)
        parts = re.split(r'\*\*(.+?)\*\*[：:]', body)
        # parts = [pre, label1, content1, label2, content2, ...]
        if len(parts) >= 3:
            i = 1
            while i + 1 < len(parts):
                label   = parts[i].strip()
                content = parts[i + 1].strip()
                content_html = _inline(content).replace('\n', '<br>')
                rows_html += (
                    f'<div class="audience-row">'
                    f'<div class="row-label">{label}</div>'
                    f'<div class="row-content">{content_html}</div>'
                    f'</div>'
                )
                i += 2
        else:
            rows_html = f'<div class="row-content">{_inline(body)}</div>'

        html.append(
            f'<div class="audience-card">'
            f'<div class="audience-header">🎯 {header}</div>'
            f'<div class="audience-body">{rows_html}</div>'
            f'</div>'
        )
    return ''.join(html) if html else _render_body(text)


def _render_diagram(text: str) -> str:
    """Render ASCII industry structure diagram in styled pre block."""
    # Extract code fence content if present
    fence = re.search(r'```[^\n]*\n(.*?)```', text, re.DOTALL)
    diagram = fence.group(1).rstrip() if fence else text.strip()
    # Escape HTML
    diagram = diagram.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Highlight arrows and nodes
    diagram = re.sub(r'(↓|→|←|↑|⟶|➔)', r'<span class="arrow">\1</span>', diagram)
    # Highlight bracketed nodes [xxx] or plain CAPS words
    diagram = re.sub(r'\[([^\]]+)\]', r'[<span class="node">\1</span>]', diagram)
    return f'<div class="industry-diagram">{diagram}</div>'


def _render_incentive_section(text: str) -> str:
    """Render incentive analysis: table + free-text notes."""
    html = []
    lines = text.split('\n')
    table_lines = []
    note_lines  = []
    in_table = False

    for line in lines:
        if line.strip().startswith('|'):
            in_table = True
            table_lines.append(line)
        else:
            if in_table and table_lines:
                html.append(_render_incentive_table(table_lines))
                table_lines = []
                in_table = False
            note_lines.append(line)

    if table_lines:
        html.append(_render_incentive_table(table_lines))
    if note_lines:
        notes = '\n'.join(note_lines).strip()
        if notes:
            html.append(_render_body(notes))

    return ''.join(html)


def _render_incentive_table(lines: list) -> str:
    """Render incentive markdown table with colour-coded strength and attitude."""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)

    data_rows = [r for r in rows if not all(re.match(r'^[-:\s]+$', c) for c in r)]
    if not data_rows:
        return ""

    header = data_rows[0]
    body_rows = data_rows[1:]

    def style_cell(text: str, col_idx: int, header_row: list) -> str:
        col_name = header_row[col_idx].lower() if col_idx < len(header_row) else ""
        t = _inline(text)
        if '強度' in col_name or 'strength' in col_name:
            if '🔴' in t or '高' in t:
                return f'<span class="incentive-high">{t}</span>'
            elif '🟡' in t or '中' in t:
                return f'<span class="incentive-mid">{t}</span>'
            elif '🟢' in t or '低' in t:
                return f'<span class="incentive-low">{t}</span>'
        if '態度' in col_name or 'attitude' in col_name:
            if any(w in t for w in ['積極', '支持', '主導']):
                return f'<span class="attitude-pos">{t}</span>'
            elif any(w in t for w in ['觀望', '被動', '跟進']):
                return f'<span class="attitude-watch">{t}</span>'
            elif any(w in t for w in ['抵制', '抵抗', '反對']):
                return f'<span class="attitude-neg">{t}</span>'
        return t

    th = ''.join(f'<th>{_inline(c)}</th>' for c in header)
    trs = ''
    for row in body_rows:
        tds = ''
        for ci, cell in enumerate(row):
            tds += f'<td>{style_cell(cell, ci, header)}</td>'
        trs += f'<tr>{tds}</tr>'

    return f'<table class="ana-table"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


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
