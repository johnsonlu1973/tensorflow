"""
Run Agent 1 (Intel Collector) and save output to sessions/.

Usage:
    python run.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load env vars from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import SESSIONS_DIR
from intel_collector import IntelCollector
from models import IntelReport
from web_search import log


FIELD_ORDER = [
    ("competitor_dynamics", "SoC 競爭動態 (Apple / Qualcomm / MediaTek)"),
    ("oem_moves", "OEM 動態 (中國 OEM / Samsung)"),
    ("ecosystem_updates", "生態 / 軟體 (Google / Android / Gemini)"),
    ("operator_dynamics", "電信商動態"),
    ("app_trends", "應用趨勢 (Killer App / Super App)"),
    ("cpe_updates", "CPE 動態 (家用路由器 / Wi-Fi 7)"),
    ("tech_6g", "6G 技術 / 標準 (IMT-2030 / 3GPP)"),
    ("chip_6g_moves", "手機 + 晶片商 6G 動態"),
    ("industry_structure", "產業結構 (購併 / 投資 / 政策)"),
]


def _get_items(report: IntelReport, field: str) -> list:
    return getattr(report, field, [])


def save_report(report: IntelReport, session_dir: Path) -> tuple[Path, Path]:
    session_dir.mkdir(parents=True, exist_ok=True)

    json_path = session_dir / "1_intel_output.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json.loads(report.model_dump_json()), f, ensure_ascii=False, indent=2)

    md_path = session_dir / "1_intel_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_build_markdown(report))

    return json_path, md_path


def _build_markdown(report: IntelReport) -> str:
    date_str = report.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Daily Intel Report — {date_str}",
        "",
    ]

    total = 0
    for field, label in FIELD_ORDER:
        items = _get_items(report, field)
        total += len(items)
        lines.append(f"## {label}（{len(items)} 則）")
        lines.append("")
        if not items:
            lines.append("_今日無相關新聞_")
            lines.append("")
            continue
        for item in items:
            src_link = f"[{item.source_name}]({item.source_url})" if item.source_url else item.source_name
            date_tag = f" · {item.published_date}" if item.published_date else ""
            lines.append(f"### {item.title}")
            lines.append(f"**來源：** {src_link}{date_tag}  ")
            lines.append(f"**類型：** {item.event_type}")
            lines.append("")
            lines.append(item.summary)
            lines.append("")
            lines.append(f"> **影響評估：** {item.impact_assessment}")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append(f"## 統計")
    lines.append(f"- 總計 {total} 則情報")
    lines.append(f"- 來源數量：{len(report.all_sources)}")
    lines.append(f"- 搜尋查詢數：{len(report.search_queries_used)}")
    lines.append("")
    if report.all_sources:
        lines.append("## 所有來源")
        for url in report.all_sources:
            lines.append(f"- {url}")

    return "\n".join(lines)


def print_summary(report: IntelReport) -> None:
    print("\n" + "=" * 70)
    print(f"  Daily Intel Report — {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    for field, label in FIELD_ORDER:
        items = _get_items(report, field)
        print(f"\n【{label}】({len(items)} 則)")
        if not items:
            print("  （今日無相關新聞）")
            continue
        for item in items:
            src = f" [{item.source_name}]" if item.source_name else ""
            print(f"  • {item.title}{src}")
            print(f"    {item.summary}")
            print(f"    → {item.impact_assessment}")
    print(f"\n來源數量：{len(report.all_sources)}")
    print("=" * 70)


LATEST_JSON = Path(__file__).parent / "latest_intel_output.json"
LATEST_MD = Path(__file__).parent / "latest_intel_report.md"


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    session_dir = SESSIONS_DIR / ts

    collector = IntelCollector()
    report = collector.run()

    # Save timestamped copies (kept for other agents)
    json_path, md_path = save_report(report, session_dir)

    # Overwrite fixed-path latest files (easy browsing)
    LATEST_JSON.write_text(
        json.dumps(json.loads(report.model_dump_json()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LATEST_MD.write_text(_build_markdown(report), encoding="utf-8")

    print_summary(report)

    log(f"[run.py] Session → {json_path}")
    log(f"[run.py] Latest  → {LATEST_MD}")


if __name__ == "__main__":
    main()
