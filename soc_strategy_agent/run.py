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

CATEGORY_LABELS = {
    "competitor_dynamics": "SoC 競爭動態 (Apple/Qualcomm/MediaTek)",
    "oem_moves": "OEM 動態 (中/韓)",
    "ecosystem_updates": "生態/軟體 (Google/Android)",
    "operator_dynamics": "電信商動態",
    "app_trends": "應用趨勢 (Killer/Super App)",
    "cpe_updates": "CPE 動態",
    "tech_6g": "6G 技術/標準",
    "chip_6g_moves": "手機/晶片商 6G 動態",
    "industry_structure": "產業結構 (購併/投資)",
}


def save_report(report: IntelReport, session_dir: Path) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    out_path = session_dir / "1_intel_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            json.loads(report.model_dump_json()),
            f,
            ensure_ascii=False,
            indent=2,
        )
    return out_path


def print_summary(report: IntelReport) -> None:
    print("\n" + "=" * 70)
    print(f"  Daily Intel Report — {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    field_map = {
        "competitor_dynamics": report.competitor_dynamics,
        "oem_moves": report.oem_moves,
        "ecosystem_updates": report.ecosystem_updates,
        "operator_dynamics": report.operator_dynamics,
        "app_trends": report.app_trends,
        "cpe_updates": report.cpe_updates,
        "tech_6g": report.tech_6g,
        "chip_6g_moves": report.chip_6g_moves,
        "industry_structure": report.industry_structure,
    }

    for field_name, items in field_map.items():
        label = CATEGORY_LABELS.get(field_name, field_name)
        count = len(items)
        print(f"\n【{label}】({count} 則)")
        if not items:
            print("  （今日無相關新聞）")
            continue
        for item in items[:3]:
            src = f" [{item.source_name}]" if item.source_name else ""
            print(f"  • {item.title}{src}")
            print(f"    {item.summary[:100]}{'…' if len(item.summary) > 100 else ''}")

    print(f"\n來源數量：{len(report.all_sources)}")
    print("=" * 70)


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    session_dir = SESSIONS_DIR / ts

    collector = IntelCollector()
    report = collector.run()

    out_path = save_report(report, session_dir)
    print_summary(report)

    log(f"[run.py] Saved to {out_path}")


if __name__ == "__main__":
    main()
