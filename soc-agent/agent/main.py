#!/usr/bin/env python3
"""
SOC Strategy Agent - Main Orchestrator
Identity : VP of Product BU & Strategy Planning
Mission  : Develop the world's strongest Agentic Mobile & CPE SoC
Success  : Pricing power | Market share growth | Customer lock-in

Data flow (no redundant searches):
  industry  → search web → save data/latest_industry.json → HTML
  usecase   → load data/latest_industry.json (no search)  → HTML
  strategy  → load data/latest_usecase.json  (no search)  → HTML
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure agent dir is on path
sys.path.insert(0, str(Path(__file__).parent))

from search_agent import SearchAgent
from report_generator import ReportGenerator
from feedback_processor import FeedbackProcessor
from slack_notifier import SlackNotifier

DATA_DIR = Path(__file__).parent.parent / "data"
INDUSTRY_CACHE = DATA_DIR / "latest_industry.json"
USECASE_CACHE  = DATA_DIR / "latest_usecase.json"


def load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def main():
    parser = argparse.ArgumentParser(description="SOC Strategy Agent")
    parser.add_argument(
        "--task",
        choices=["industry", "usecase", "strategy", "feedback"],
        required=True,
    )
    args = parser.parse_args()

    config = load_config()
    notifier = SlackNotifier()
    generator = ReportGenerator(config)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] Task: {args.task}", flush=True)

    try:
        if args.task == "industry":
            # Search → save → HTML
            searcher = SearchAgent(config)
            data = searcher.search_industry_news()
            save_json(INDUSTRY_CACHE, data)
            print(f"Industry data saved to {INDUSTRY_CACHE}", flush=True)
            path, url = generator.generate_industry_report(data)
            notifier.send(
                title="産業動態報告已更新",
                report_type="Industry Dynamics",
                url=url,
                summary=data.get("summary", ""),
                highlights=data.get("highlights", []),
            )

        elif args.task == "usecase":
            # Load cached industry data — no web search
            data = load_json(INDUSTRY_CACHE)
            if data:
                print(f"Loaded industry data from {INDUSTRY_CACHE}", flush=True)
            else:
                print("No cached industry data found — run 'industry' task first.", flush=True)
                data = {"summary": "", "categories": {}, "highlights": [],
                        "all_sources": [], "market_signals": []}
            path, url = generator.generate_usecase_report(data)
            # Save use-case analysis result for strategy to use
            save_json(USECASE_CACHE, {
                "summary": generator.last_summary,
                "highlights": generator.last_highlights,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            })
            notifier.send(
                title="使用場景與痛點報告已更新",
                report_type="Use Case & Pain Points",
                url=url,
                summary=generator.last_summary,
                highlights=generator.last_highlights,
            )

        elif args.task == "strategy":
            # Load cached use-case data — no web search
            uc_data = load_json(USECASE_CACHE)
            if uc_data:
                print(f"Loaded use-case data from {USECASE_CACHE}", flush=True)
            else:
                print("No cached use-case data — strategy will use recent HTML reports.", flush=True)
            path, url = generator.generate_strategy_report()
            notifier.send(
                title="策略建議報告已更新",
                report_type="Strategy Recommendations",
                url=url,
                summary=generator.last_summary,
                highlights=generator.last_highlights,
            )

        elif args.task == "feedback":
            processor = FeedbackProcessor(config)
            new_skills = processor.process_github_issues()
            print(f"Learned {len(new_skills)} new skills from feedback", flush=True)

        print(f"Task '{args.task}' completed successfully.", flush=True)

    except Exception as exc:
        print(f"ERROR in task '{args.task}': {exc}", file=sys.stderr, flush=True)
        notifier.send_error(args.task, str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
