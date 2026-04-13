#!/usr/bin/env python3
"""
SOC Strategy Agent - Main Orchestrator
Identity : VP of Product BU & Strategy Planning
Mission  : Develop the world's strongest Agentic Mobile & CPE SoC
Success  : Pricing power | Market share growth | Customer lock-in
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


def load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


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
    searcher = SearchAgent(config)
    generator = ReportGenerator(config)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] Task: {args.task}")

    try:
        if args.task == "industry":
            data = searcher.search_industry_news()
            path, url = generator.generate_industry_report(data)
            notifier.send(
                title="× 産業動態報告已更新",
                report_type="Industry Dynamics",
                url=url,
                summary=data.get("summary", ""),
                highlights=data.get("highlights", []),
            )

        elif args.task == "usecase":
            data = searcher.search_industry_news()
            path, url = generator.generate_usecase_report(data)
            notifier.send(
                title="× 使用場景與痛點報告已更新",
                report_type="Use Case & Pain Points",
                url=url,
                summary=generator.last_summary,
                highlights=generator.last_highlights,
            )

        elif args.task == "strategy":
            path, url = generator.generate_strategy_report()
            notifier.send(
                title="× 策略建議報告已更新",
                report_type="Strategy Recommendations",
                url=url,
                summary=generator.last_summary,
                highlights=generator.last_highlights,
            )

        elif args.task == "feedback":
            processor = FeedbackProcessor(config)
            new_skills = processor.process_github_issues()
            print(f"Learned {len(new_skills)} new skills from feedback")

        print(f"Task '{args.task}' completed successfully.")

    except Exception as exc:
        print(f"ERROR in task '{args.task}': {exc}", file=sys.stderr)
        notifier.send_error(args.task, str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
