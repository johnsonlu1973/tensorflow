"""Build Slack Block Kit payload for SOC Planning Agent notification."""
import json
import os
import sys

new_articles = os.environ.get("NEW_ARTICLES", "0")
hot_count    = os.environ.get("HOT_COUNT", "0")
hot_summary  = os.environ.get("HOT_SUMMARY", "").strip()
tw_time      = os.environ.get("TW_TIME", "")
pages_url    = os.environ.get("PAGES_URL", "https://johnsonlu1973.github.io/tensorflow")

blocks = [
    {
        "type": "header",
        "text": {"type": "plain_text", "text": "📡 SOC Planning Agent — 發現新市場情報！", "emoji": True},
    },
    {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*📅 台灣時間*\n{tw_time}"},
            {"type": "mrkdwn", "text": f"*🆕 新文章*\n{new_articles} 篇"},
            {"type": "mrkdwn", "text": f"*🔥 重大消息*\n{hot_count} 篇"},
        ],
    },
]

if hot_summary:
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*🔥 重大消息*\n{hot_summary}"},
    })

blocks += [
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📊 查看 Dashboard"},
                "url": pages_url,
            }
        ],
    },
    {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "SOC Planning Agent · 每 2 小時自動檢查 RSS"}],
    },
]

print(json.dumps({"blocks": blocks}))
