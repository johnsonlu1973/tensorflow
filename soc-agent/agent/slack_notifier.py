"""
Slack Notifier
Sends formatted messages via Slack Incoming Webhook.
"""
import json
import os
from datetime import datetime, timezone

import requests


class SlackNotifier:
    def __init__(self):
        self.webhook = os.environ.get("SLACK_WEBHOOK_URL", "")

    def send(
        self,
        title: str,
        report_type: str,
        url: str,
        summary: str,
        highlights: list[str],
    ):
        if not self.webhook:
            print("[Slack] No webhook URL configured, skipping notification.")
            return

        hl_text = "\n".join(f"• {h}" for h in highlights[:5]) if highlights else "N/A"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title, "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*報告類型:*\n{report_type}"},
                    {"type": "mrkdwn", "text": f"*生成時間:*\n{ts}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*摘要:*\n{summary}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*重點:*\n{hl_text}"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "閱讀完整報告"},
                        "url": url,
                        "style": "primary",
                    }
                ],
            },
            {"type": "divider"},
        ]

        payload = {"blocks": blocks}
        try:
            resp = requests.post(
                self.webhook,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            print(f"[Slack] Notification sent: {title}")
        except Exception as e:
            print(f"[Slack] Failed to send notification: {e}")

    def send_error(self, task: str, error: str):
        if not self.webhook:
            return
        payload = {
            "text": f":x: *SOC Strategy Agent Error*\nTask: `{task}`\nError: {error}"
        }
        try:
            requests.post(
                self.webhook,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
        except Exception:
            pass
