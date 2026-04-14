"""
Report Generator
Generates three types of HTML reports:
  1. Industry Dynamics   (every 4 h)
  2. Use Case & Pain Points (daily)
  3. Strategy Recommendations (every 2 days)

Each report is a self-contained HTML file with:
- Professional styling
- Feedback section linked to GitHub Issues
- Skills context applied
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "johnsonlu1973/tensorflow")
GITHUB_BRANCH = "claude/soc-strategy-agent-TBegn"

# GitHub Pages URL — workflows set REPORT_BASE_URL; falls back to Pages default
REPORT_BASE_URL = os.environ.get(
    "REPORT_BASE_URL",
    "https://johnsonlu1973.github.io/tensorflow/soc-agent/reports",
)
# URL is consistent with docs/ folder in master branch:
# docs/soc-agent/reports/industry/latest.html
# → https://johnsonlu1973.github.io/tensorflow/soc-agent/reports/industry/latest.html


def _ts_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


def _now_fmt() -> str:
    from zoneinfo import ZoneInfo
    tw = datetime.now(ZoneInfo("Asia/Taipei"))
    return tw.strftime("%Y-%m-%d %H:%M CST")


def _feedback_url(report_type: str, report_file: str) -> str:
    title = f"[FEEDBACK] {report_type} - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    body = (
        f"報告類型 / Report Type: {report_type}%0A"
        f"報告檔案 / Report File: {report_file}%0A%0A"
        "## 評分 / Rating (1-5)%0A%0A"
        "## 哪些部分很好 / What worked well%0A%0A"
        "## 需要改善的地方 / What needs improvement%0A%0A"
        "## 補充建議 / Additional suggestions%0A"
    )
    return (
        f"https://github.com/{GITHUB_REPO}/issues/new"
        f"?labels=soc-feedback&title={title}&body={body}"
    )


# ---------------------------------------------------------------------------
# HTML skeleton
# ---------------------------------------------------------------------------

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --primary:#1a1f36; --accent:#4f46e5; --accent2:#06b6d4;
    --ok:#10b981; --warn:#f59e0b; --danger:#ef4444;
    --bg:#f8fafc; --card:#ffffff; --border:#e2e8f0;
    --text:#1e293b; --muted:#64748b;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
  header{{background:var(--primary);color:#fff;padding:2rem}}
  header .badge{{display:inline-block;background:var(--accent);padding:.25rem .75rem;border-radius:9999px;font-size:.75rem;margin-bottom:.75rem}}
  header h1{{font-size:1.8rem;font-weight:700;margin-bottom:.25rem}}
  header .meta{{font-size:.85rem;opacity:.7}}
  .container{{max-width:1100px;margin:0 auto;padding:2rem 1.5rem}}
  .summary-box{{background:var(--primary);color:#fff;border-radius:12px;padding:1.5rem;margin-bottom:2rem}}
  .summary-box h2{{font-size:1rem;opacity:.7;margin-bottom:.5rem}}
  .highlights{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;margin-bottom:2rem}}
  .highlight-card{{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:8px;padding:1rem}}
  .section{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
  .section h2{{font-size:1.1rem;font-weight:700;color:var(--primary);border-bottom:2px solid var(--border);padding-bottom:.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}}
  .news-list{{list-style:none}}
  .news-list li{{padding:.5rem 0;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;gap:.5rem}}
  .news-list li:last-child{{border-bottom:none}}
  .pill{{display:inline-block;font-size:.7rem;padding:.15rem .5rem;border-radius:9999px;font-weight:600}}
  .pill-ok{{background:#d1fae5;color:#065f46}}
  .pill-warn{{background:#fef3c7;color:#92400e}}
  .pill-gap{{background:#fee2e2;color:#991b1b}}
  .implication{{font-size:.85rem;color:var(--muted);margin-top:.5rem;padding:.5rem;background:var(--bg);border-radius:6px}}
  .sources{{font-size:.8rem}}
  .sources a{{color:var(--accent);text-decoration:none}}
  .sources a:hover{{text-decoration:underline}}
  .tag{{display:inline-block;background:#e0e7ff;color:var(--accent);font-size:.7rem;padding:.1rem .4rem;border-radius:4px;margin:.1rem}}
  table{{width:100%;border-collapse:collapse;font-size:.9rem}}
  th{{background:var(--primary);color:#fff;padding:.6rem 1rem;text-align:left}}
  td{{padding:.6rem 1rem;border-bottom:1px solid var(--border)}}
  tr:hover td{{background:var(--bg)}}
  .feedback-section{{background:var(--primary);color:#fff;border-radius:12px;padding:2rem;margin-top:2rem;text-align:center}}
  .feedback-section h2{{margin-bottom:.5rem}}
  .feedback-section p{{opacity:.8;margin-bottom:1.5rem;font-size:.9rem}}
  .btn{{display:inline-block;padding:.75rem 2rem;border-radius:8px;font-weight:600;text-decoration:none;transition:.2s}}
  .btn-primary{{background:var(--accent);color:#fff}}
  .btn-primary:hover{{background:#4338ca}}
  .btn-secondary{{background:transparent;border:2px solid rgba(255,255,255,.5);color:#fff;margin-left:1rem}}
  .btn-secondary:hover{{background:rgba(255,255,255,.1)}}
  .stars{{display:flex;justify-content:center;gap:.5rem;margin-bottom:1.5rem;font-size:2rem;cursor:pointer}}
  .star{{opacity:.4;transition:.2s;user-select:none}}
  .star:hover,.star.active{{opacity:1}}
  footer{{text-align:center;padding:2rem;color:var(--muted);font-size:.8rem}}
  .chip-ok{{color:var(--ok);font-weight:600}}
  .chip-warn{{color:var(--warn);font-weight:600}}
  .chip-no{{color:var(--danger);font-weight:600}}
  .strategy-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1rem}}
  .strategy-card h3{{color:var(--accent);margin-bottom:.75rem}}
  .criteria-badge{{display:inline-flex;align-items:center;gap:.4rem;background:#ede9fe;color:#5b21b6;padding:.35rem .75rem;border-radius:6px;font-size:.85rem;font-weight:600;margin:.25rem}}
</style>
</head>
<body>
"""

HTML_FOOT = """
<footer>
  <p>SOC Strategy Agent &mdash; VP Product BU &amp; Strategy Planning</p>
  <p>Mission: Develop the world's strongest Agentic Mobile &amp; CPE SoC</p>
</footer>
<script>
// Star rating for feedback
document.querySelectorAll('.stars').forEach(function(container) {
  var stars = container.querySelectorAll('.star');
  stars.forEach(function(star, i) {
    star.addEventListener('mouseenter', function() {
      stars.forEach(function(s, j) { s.classList.toggle('active', j <= i); });
    });
    star.addEventListener('mouseleave', function() {
      var sel = parseInt(container.dataset.selected || 0);
      stars.forEach(function(s, j) { s.classList.toggle('active', j < sel); });
    });
    star.addEventListener('click', function() {
      container.dataset.selected = i + 1;
      var url = container.dataset.url + encodeURIComponent('\nRating: ' + (i+1) + '/5');
      container.nextElementSibling.href = url;
    });
  });
});
</script>
</body>
</html>
"""


def _feedback_block(report_type: str, filename: str) -> str:
    url = _feedback_url(report_type, filename)
    return f"""
<div class="feedback-section">
  <h2>&#128172; 提供您的回饋 / Share Your Feedback</h2>
  <p>您的回饋將直接訓練 agent，改善未來的報告品質。<br>
     Your feedback directly trains the agent and improves future reports.</p>
  <div class="stars" data-selected="0" data-url="{url}">
    <span class="star">&#9733;</span>
    <span class="star">&#9733;</span>
    <span class="star">&#9733;</span>
    <span class="star">&#9733;</span>
    <span class="star">&#9733;</span>
  </div>
  <a href="{url}" target="_blank" class="btn btn-primary">&#128221; 提交詳細回饋（GitHub Issue）</a>
  <a href="https://github.com/{GITHUB_REPO}/issues?q=label%3Asoc-feedback"
     target="_blank" class="btn btn-secondary">檢視過去回饋</a>
</div>
"""


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        # Write reports into docs/soc-agent/reports/ so GitHub Pages
        # (served from master/docs/) can render them directly.
        self.reports_dir = Path(__file__).parent.parent.parent / "docs" / "soc-agent" / "reports"
        self.last_summary = ""
        self.last_highlights: list[str] = []

    # ------------------------------------------------------------------ #
    #  1. Industry Dynamics Report                                         #
    # ------------------------------------------------------------------ #

    def generate_industry_report(self, data: dict) -> tuple[str, str]:
        ts = _ts_label()
        filename = f"industry_{ts}.html"
        out_dir = self.reports_dir / "industry"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        categories = data.get("categories", {})
        sources = data.get("all_sources", [])
        signals = data.get("market_signals", [])

        cat_labels = {
            "apple": ("🍎", "Apple"),
            "qualcomm": ("📡", "Qualcomm"),
            "mediatek": ("📶", "MediaTek"),
            "chinese_oems": ("🇨🇳", "Chinese OEMs"),
            "samsung": ("🌀", "Samsung"),
            "android_ecosystem": ("🤖", "Android Ecosystem"),
            "network_operators": ("📡", "Network Operators"),
            "ai_agent_apps": ("🧠", "AI Agent / Apps"),
            "6g_technology": ("🚀", "6G Technology"),
            "cpe_devices": ("🏠", "CPE Devices"),
        }

        sections_html = ""
        for key, (icon, label) in cat_labels.items():
            cat = categories.get(key, {})
            news_items = cat.get("news", [])
            impl = cat.get("implications", "")
            if not news_items and not impl:
                continue
            items_html = "".join(
                f"<li><span>▸</span>{item}</li>" for item in news_items
            )
            sections_html += f"""
<div class="section">
  <h2>{icon} {label}</h2>
  <ul class="news-list">{items_html}</ul>
  {"<div class='implication'>💡 <strong>SoC 戰略意涵：</strong>" + impl + "</div>" if impl else ""}
</div>"""

        signals_html = "".join(f"<li><span>⚡</span>{s}</li>" for s in signals)
        sources_html = "".join(
            f'<tr><td><a href="{s.get("url","#")}" target="_blank">'
            f'{s.get("title","")}</a></td>'
            f'<td>{s.get("date","")}</td>'
            f'<td><span class="pill pill-ok">{s.get("credibility","media")}</span></td></tr>'
            for s in sources[:30]
        )
        highlights_html = "".join(
            f'<div class="highlight-card">{h}</div>'
            for h in data.get("highlights", [])
        )

        html = (
            HTML_HEAD.format(title=f"產業動態報告 {_now_fmt()}")
            + f"""
<header>
  <div class="badge">Industry Dynamics Report</div>
  <h1>🌐 產業動態報告</h1>
  <div class="meta">Generated: {_now_fmt()} &nbsp;|&nbsp; SOC Strategy Agent &nbsp;|&nbsp; VP Product BU</div>
</header>
<div class="container">
  <div class="summary-box">
    <h2>Executive Summary</h2>
    <p>{data.get("summary","")}</p>
  </div>
  <div class="highlights">{highlights_html}</div>
  {sections_html}
  {"<div class='section'><h2>⚡ 市場信號 Market Signals</h2><ul class='news-list'>" + signals_html + "</ul></div>" if signals else ""}
  <div class="section">
    <h2>📚 資料來源 Sources</h2>
    <table class="sources">
      <tr><th>標題</th><th>日期</th><th>可信度</th></tr>
      {sources_html}
    </table>
  </div>
  {_feedback_block("產業動態報告", filename)}
</div>"""
            + HTML_FOOT
        )

        out_path.write_text(html, encoding="utf-8")
        # Also write as latest
        (out_dir / "latest.html").write_text(html, encoding="utf-8")

        url = f"{REPORT_BASE_URL}/industry/latest.html"
        self.last_summary = data.get("summary", "")
        self.last_highlights = data.get("highlights", [])
        print(f"Industry report saved: {out_path}")
        return str(out_path), url

    # ------------------------------------------------------------------ #
    #  2. Use Case & Pain Points Report                                    #
    # ------------------------------------------------------------------ #

    def generate_usecase_report(self, data: dict) -> tuple[str, str]:
        from chip_analyzer import ChipAnalyzer
        from knowledge_graph import KnowledgeGraph
        ts = _ts_label()
        filename = f"usecase_{ts}.html"
        out_dir = self.reports_dir / "use-cases"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        analysis = self._analyze_usecases(data)
        chip = analysis.get("chip_analysis", {})
        current_uc = analysis.get("current_use_cases", [])

        # Use knowledge graph to predict 2-year future use cases (graph-driven, not just AI guessing)
        kg = KnowledgeGraph(self.config)
        current_titles = [u.get("title", "") for u in current_uc]
        kg_predictions = kg.predict_future_use_cases(current_titles)

        # Merge KG predictions with any from analysis, de-duplicate
        analysis_future = analysis.get("future_use_cases_2y", [])
        kg_future_titles = {p.get("use_case", "") for p in kg_predictions}
        future_uc = list(analysis_future) + [
            {
                "title": p.get("use_case", ""),
                "description": p.get("description", ""),
                "pain_points": p.get("pain_point_addressed", ""),
                "chip_requirement": p.get("chip_requirement", ""),
                "confidence": p.get("confidence", 0),
                "graph_path": p.get("graph_path", ""),
                "source": "knowledge_graph",
            }
            for p in kg_predictions
            if p.get("use_case") not in {u.get("title") for u in analysis_future}
        ]

        # Use ChipAnalyzer with the actual spec files for accurate evaluation
        all_uc_titles = [u.get("title", "") for u in current_uc + future_uc]
        chip_result = ChipAnalyzer(self.config).analyze(all_uc_titles)
        evaluations = {e["use_case"]: e for e in chip_result.get("evaluations", [])}
        known_gaps = ChipAnalyzer(self.config).get_known_gaps()
        kg_stats = kg.get_stats()

        status_map = {
            "yes":     ("chip-ok",   "✅ 可滿足"),
            "partial": ("chip-warn", "⚠️ 部分滿足"),
            "no":      ("chip-no",   "❌ 無法滿足"),
            "unknown": ("",          "— 未知"),
        }

        def uc_row(uc: dict, show_graph_path: bool = False) -> str:
            title = uc.get("title", "")
            pain  = uc.get("pain_points", "")
            ev    = evaluations.get(title, {})
            qs, qt = status_map.get(ev.get("qualcomm_status","unknown"), ("","—"))
            ms, mt = status_map.get(ev.get("mediatek_status","unknown"), ("","—"))
            qr = ev.get("qualcomm_reason","")
            mr = ev.get("mediatek_reason","")
            gap = ev.get("gap_notes","")
            graph_path = uc.get("graph_path","")
            chip_req   = uc.get("chip_requirement","")
            confidence = uc.get("confidence", None)
            is_kg = uc.get("source") == "knowledge_graph"

            subtitle = uc.get("description","")
            if show_graph_path and graph_path:
                subtitle += f"<br><span style='font-size:.72rem;color:#6366f1'>🔗 Graph: {graph_path}</span>"
            if chip_req:
                subtitle += f"<br><span style='font-size:.72rem;color:var(--warn)'>⚙️ SoC需求: {chip_req}</span>"
            conf_badge = (f" <span class='pill pill-ok'>信心 {int(confidence*100)}%</span>"
                          if confidence else "")
            kg_badge = " <span class='pill' style='background:#ede9fe;color:#6d28d9'>KG預測</span>" if is_kg else ""

            gap_row = (f"<tr><td colspan='4' style='font-size:.8rem;color:var(--warn);"
                       f"background:#fffbeb'><strong>差距:</strong> {gap}</td></tr>") if gap else ""
            return (
                f"<tr><td><strong>{title}</strong>{kg_badge}{conf_badge}<br>"
                f"<small style='color:var(--muted)'>{subtitle}</small></td>"
                f"<td>{pain}</td>"
                f"<td class='{qs}'>{qt}<br><small style='font-weight:400;color:var(--muted)'>{qr}</small></td>"
                f"<td class='{ms}'>{mt}<br><small style='font-weight:400;color:var(--muted)'>{mr}</small></td></tr>"
                + gap_row
            )

        cur_rows = "".join(uc_row(u, show_graph_path=False) for u in current_uc)
        fut_rows = "".join(uc_row(u, show_graph_path=True)  for u in future_uc)

        highlights_html = "".join(
            f'<div class="highlight-card">{h}</div>'
            for h in analysis.get("highlights", [])
        )

        html = (
            HTML_HEAD.format(title=f"使用場景與需求痛點報告 {_now_fmt()}")
            + f"""
<header>
  <div class="badge">Use Case &amp; Pain Points — Daily Report</div>
  <h1>🎯 使用場景與需求痛點分析</h1>
  <div class="meta">Generated: {_now_fmt()} &nbsp;|&nbsp; 分析期間：過去 24 小時</div>
</header>
<div class="container">
  <div class="summary-box">
    <h2>Executive Summary</h2>
    <p>{analysis.get("summary","")}</p>
    <p style="margin-top:.75rem;font-size:.8rem;opacity:.7">
      Knowledge Graph: {kg_stats.get("nodes",0)} nodes · {kg_stats.get("edges",0)} edges
      · 2-year predictions driven by graph paths
    </p>
  </div>
  <div class="highlights">{highlights_html}</div>

  <div class="section">
    <h2>📱 當前使用場景 Current Use Cases (Now)</h2>
    <table>
      <tr><th>場景</th><th>需求痛點</th>
          <th>Qualcomm ({chip.get("qualcomm",{}).get("chip_model","Snapdragon")})</th>
          <th>MediaTek ({chip.get("mediatek",{}).get("chip_model","Dimensity")})</th>
      </tr>
      {cur_rows}
    </table>
  </div>

  <div class="section">
    <h2>🔮 2年後使用場景 Future Use Cases (2-Year Horizon)</h2>
    <table>
      <tr><th>場景</th><th>預期痛點</th>
          <th>Qualcomm 能否滿足</th><th>MediaTek 能否滿足</th>
      </tr>
      {fut_rows}
    </table>
  </div>

  <div class="section">
    <h2>🔍 晶片差距分析 Chip Gap Analysis</h2>
    <p style="color:var(--muted);margin-bottom:1rem">以下場景目前晶片方案無法滿足，將納入策略建議報告</p>
    {"".join(f'<span class="tag">⚠️ {g}</span>' for g in analysis.get("unmet_gaps",[]))}
    {"".join(f'<span class="tag" style="background:#fee2e2;color:#991b1b">🔴 {g}</span>' for g in known_gaps) if known_gaps else ""}
  </div>

  {_feedback_block("使用場景與需求痛點報告", filename)}
</div>"""
            + HTML_FOOT
        )

        out_path.write_text(html, encoding="utf-8")
        (out_dir / "latest.html").write_text(html, encoding="utf-8")

        url = f"{REPORT_BASE_URL}/use-cases/latest.html"
        self.last_summary = analysis.get("summary", "")
        self.last_highlights = analysis.get("highlights", [])
        print(f"Use-case report saved: {out_path}")
        return str(out_path), url

    def _analyze_usecases(self, data: dict) -> dict:
        skills_ctx = self._skills_context()
        prompt = f"""You are the VP of Product BU & Strategy Planning at a SOC company.
Mission: Develop the world's strongest Agentic Mobile & CPE SoC.

Based on this industry data from the past 24 hours:
{json.dumps(data, indent=2, ensure_ascii=False)[:6000]}
{skills_ctx}

Identify use cases and pain points. Return ONLY valid JSON:
{{
  "summary": "executive summary in Traditional Chinese",
  "highlights": ["5 key findings"],
  "current_use_cases": [
    {{
      "title": "use case name",
      "description": "brief description",
      "pain_points": "current pain points for OEM / users"
    }}
  ],
  "future_use_cases_2y": [
    {{
      "title": "future use case",
      "description": "description",
      "pain_points": "anticipated pain points"
    }}
  ],
  "chip_analysis": {{
    "qualcomm": {{
      "chip_model": "Snapdragon 8 Elite",
      "satisfies": ["use case titles that this chip can satisfy"]
    }},
    "mediatek": {{
      "chip_model": "Dimensity 9400",
      "satisfies": ["use case titles that this chip can satisfy"]
    }}
  }},
  "unmet_gaps": ["gaps not satisfied by either chip"]
}}"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6144,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"Use-case analysis error: {e}")
        return {
            "summary": "Analysis pending.",
            "highlights": [],
            "current_use_cases": [],
            "future_use_cases_2y": [],
            "chip_analysis": {},
            "unmet_gaps": [],
        }

    # ------------------------------------------------------------------ #
    #  3. Strategy Recommendations Report                                  #
    # ------------------------------------------------------------------ #

    def generate_strategy_report(self) -> tuple[str, str]:
        from knowledge_graph import KnowledgeGraph
        from memory_manager import MemoryManager
        ts = _ts_label()
        filename = f"strategy_{ts}.html"
        out_dir = self.reports_dir / "strategy"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        # Load confirmed facts from memory to ground strategy in real data
        mem = MemoryManager(self.config)
        confirmed_facts = mem.get_confirmed_facts()

        strategy = self._build_strategy(confirmed_facts)
        recs = strategy.get("recommendations", [])

        # Enrich each strategy with all related use cases from knowledge graph
        kg = KnowledgeGraph(self.config)
        enriched = kg.link_strategy_to_use_cases(recs)
        # Merge enriched data back into recs
        enriched_map = {e.get("title", ""): e for e in enriched}
        for rec in recs:
            enr = enriched_map.get(rec.get("title", ""), {})
            if enr:
                rec["secondary_use_cases"] = enr.get("secondary_use_cases", [])
                rec["ecosystem_connections"] = enr.get("ecosystem_connections", [])
        kg_stats = kg.get_stats()
        criteria = strategy.get("success_criteria_met", {})

        def badge(met: bool, label: str) -> str:
            cls = "pill-ok" if met else "pill-warn"
            icon = "✅" if met else "⚠️"
            return f'<span class="pill {cls}">{icon} {label}</span>'

        criteria_html = (
            badge(criteria.get("pricing_power", False), "定價權 Pricing Power")
            + badge(criteria.get("market_share", False), "市占率 Market Share")
            + badge(criteria.get("customer_lock_in", False), "客戶綁定 Lock-in")
        )

        recs_html = ""
        for i, rec in enumerate(recs, 1):
            hw = "".join(f"<li>{x}</li>" for x in rec.get("hardware_strategy", []))
            sw = "".join(f"<li>{x}</li>" for x in rec.get("software_strategy", []))
            eco = "".join(f"<li>{x}</li>" for x in rec.get("ecosystem_strategy", []))
            oem = rec.get("oem_value", "")
            biz = rec.get("business_model", "")
            pain_solved = "".join(f'<span class="tag">{p}</span>' for p in rec.get("pain_points_solved", []))
            recs_html += f"""
<div class="strategy-card">
  <h3>#{i} {rec.get("title","")}</h3>
  <p>{rec.get("description","")}</p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem">
    <div>
      <strong>🔧 硬體策略 Hardware</strong>
      <ul style="margin-top:.5rem;padding-left:1.2rem">{hw}</ul>
    </div>
    <div>
      <strong>💻 軟體策略 Software</strong>
      <ul style="margin-top:.5rem;padding-left:1.2rem">{sw}</ul>
    </div>
  </div>
  {"<div style='margin-top:1rem'><strong>🌐 生態策略 Ecosystem</strong><ul style='margin-top:.5rem;padding-left:1.2rem'>" + eco + "</ul></div>" if eco else ""}
  <div style="margin-top:1rem;padding:.75rem;background:var(--bg);border-radius:8px">
    <strong>💼 對 OEM 的價值 OEM Value:</strong> {oem}
  </div>
  <div style="margin-top:.5rem;padding:.75rem;background:var(--bg);border-radius:8px">
    <strong>💰 商業模式 Business Model:</strong> {biz}
  </div>
  <div style="margin-top:.75rem"><strong>解決的痛點：</strong> {pain_solved}</div>
  <div style="margin-top:.5rem">
    {"".join(badge(True, c) for c in rec.get("success_criteria_achieved",[]))}
  </div>
</div>"""

        highlights_html = "".join(
            f'<div class="highlight-card">{h}</div>'
            for h in strategy.get("highlights", [])
        )

        html = (
            HTML_HEAD.format(title=f"策略建議報告 {_now_fmt()}")
            + f"""
<header>
  <div class="badge">Strategy Recommendations — Bi-Daily</div>
  <h1>🏆 SoC 產品策略建議</h1>
  <div class="meta">Generated: {_now_fmt()} &nbsp;|&nbsp; VP Product BU &amp; Strategy Planning</div>
</header>
<div class="container">
  <div class="summary-box">
    <h2>Executive Summary</h2>
    <p>{strategy.get("summary","")}</p>
    <div style="margin-top:1rem">{criteria_html}</div>
    <p style="margin-top:.75rem;font-size:.8rem;opacity:.7">
      Knowledge Graph: {kg_stats.get("nodes",0)} nodes · {kg_stats.get("edges",0)} edges
      · Strategy grounded in {len(confirmed_facts)} confirmed market facts
    </p>
  </div>
  <div class="highlights">{highlights_html}</div>

  <div class="section">
    <h2>📊 策略建議 Strategic Recommendations</h2>
    {recs_html}
  </div>

  <div class="section">
    <h2>⚠️ 未解決的場景缺口 Unresolved Gaps</h2>
    {"".join(f'<span class="tag">{g}</span>' for g in strategy.get("unresolved_gaps",[]))}
    <p style="margin-top:.75rem;color:var(--muted);font-size:.85rem">
      以上場景將在後續兩天報告中持續追蹤。
    </p>
  </div>

  {_feedback_block("策略建議報告", filename)}
</div>"""
            + HTML_FOOT
        )

        out_path.write_text(html, encoding="utf-8")
        (out_dir / "latest.html").write_text(html, encoding="utf-8")

        url = f"{REPORT_BASE_URL}/strategy/latest.html"
        self.last_summary = strategy.get("summary", "")
        self.last_highlights = strategy.get("highlights", [])
        print(f"Strategy report saved: {out_path}")
        return str(out_path), url

    def _build_strategy(self, confirmed_facts: list | None = None) -> dict:
        # Gather unmet gaps from recent use-case reports
        gaps = self._collect_recent_gaps()
        skills_ctx = self._skills_context()
        facts_ctx = ""
        if confirmed_facts:
            facts_ctx = (
                "\n\nConfirmed market facts (verified across multiple search runs — ground strategy in these):\n"
                + "\n".join(f"- {f}" for f in confirmed_facts[:20])
            )
        prompt = f"""You are the VP of Product BU & Strategy Planning at a leading SOC company.
Mission: Develop the world's strongest Agentic Mobile & CPE SoC.
Success criteria (must achieve at least ONE): pricing power | market share growth | customer lock-in.

Based on these unmet use cases and gaps that current Qualcomm/MediaTek chips cannot satisfy:
{json.dumps(gaps, ensure_ascii=False, indent=2)}
{facts_ctx}
{skills_ctx}

Propose concrete SoC product strategies. Validate each against:
1. Does it solve OEM pain points?
2. Does it meet OEM needs?
3. Does it achieve at least one success criterion?

Return ONLY valid JSON:
{{
  "summary": "executive summary in Traditional Chinese",
  "highlights": ["5 key points"],
  "recommendations": [
    {{
      "title": "strategy title",
      "description": "detailed description",
      "hardware_strategy": ["hw item 1", "hw item 2"],
      "software_strategy": ["sw item 1", "sw item 2"],
      "ecosystem_strategy": ["eco item"],
      "oem_value": "clear value proposition to OEM customers",
      "business_model": "recommended business model",
      "pain_points_solved": ["pain1", "pain2"],
      "success_criteria_achieved": ["pricing_power | market_share | customer_lock_in"]
    }}
  ],
  "success_criteria_met": {{
    "pricing_power": false,
    "market_share": false,
    "customer_lock_in": false
  }},
  "unresolved_gaps": ["gaps that still need future solutions"]
}}"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"Strategy build error: {e}")
        return {
            "summary": "Strategy pending.",
            "highlights": [],
            "recommendations": [],
            "success_criteria_met": {},
            "unresolved_gaps": [],
        }

    def _collect_recent_gaps(self) -> list[str]:
        """Collect unmet gaps from the two most recent use-case reports."""
        gaps: list[str] = []
        uc_dir = self.reports_dir / "use-cases"
        if not uc_dir.exists():
            return gaps
        files = sorted(uc_dir.glob("usecase_*.html"), reverse=True)[:2]
        for f in files:
            text = f.read_text(encoding="utf-8", errors="ignore")
            # Quick heuristic: extract tag content between ⚠️ markers
            found = re.findall(r"⚠️\s*([^<]+)", text)
            gaps.extend(f.strip() for f in found if f.strip())
        return list(set(gaps))[:30]

    def _skills_context(self) -> str:
        path = Path(__file__).parent.parent / "skills" / "learned_skills.json"
        if not path.exists():
            return ""
        with open(path, encoding="utf-8") as f:
            skills = json.load(f).get("skills", [])
        if not skills:
            return ""
        snippets = [s["prompt_addition"] for s in skills[:8]]
        return "\n\nApply these learned skills:\n" + "\n".join(f"- {s}" for s in snippets)
