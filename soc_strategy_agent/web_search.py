"""
Web search: Perplexity API (primary) + Claude web_search tool (fallback).
Ported from soc-agent/agent/search_agent.py with today-only filtering.
"""
import json
import re
import time
from datetime import datetime, timezone

import anthropic
import requests

from config import ANTHROPIC_API_KEY, PERPLEXITY_API_KEY

CLAUDE_CALL_INTERVAL = 8  # seconds between Claude API calls


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


class WebSearch:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.perplexity_key = PERPLEXITY_API_KEY
        self._last_claude_call = 0.0

    def search(self, query: str) -> dict:
        if self.perplexity_key:
            result = self._perplexity(query)
            if result:
                return result
        return self._claude_search(query)

    def _perplexity(self, query: str) -> dict | None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.perplexity_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a semiconductor and mobile industry analyst. "
                        "Provide factual, sourced information ONLY from credible media: "
                        "Reuters, Bloomberg, Nikkei, The Verge, IEEE, TechCrunch, "
                        "official company blogs (qualcomm.com, mediatek.com, apple.com, samsung.com), "
                        "Counterpoint Research, IDC, SemiAnalysis. "
                        "Exclude personal blogs and unverified social media. "
                        "ONLY return news published today. Discard anything older."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"News published TODAY ({today}) about: {query}\n\n"
                        f"IMPORTANT: Only include articles published on {today}. "
                        "Return JSON with keys: findings (list of str), "
                        "sources (list of {title, url, date}), significance (str)"
                    ),
                },
            ],
            "return_citations": True,
            "search_recency_filter": "day",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            return {
                "query": query,
                "content": data["choices"][0]["message"]["content"],
                "citations": data.get("citations", []),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            log(f"  Perplexity failed ({type(e).__name__}), falling back to Claude")
            return None

    def _claude_search(self, query: str) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        elapsed = time.time() - self._last_claude_call
        if elapsed < CLAUDE_CALL_INTERVAL:
            time.sleep(CLAUDE_CALL_INTERVAL - elapsed)

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Search for news published TODAY ({today}) about: {query}. "
                            "Only include articles from today. Discard anything older. "
                            "Focus on credible sources only: Reuters, Bloomberg, Nikkei, "
                            "The Verge, IEEE, TechCrunch, official company sites. "
                            "Return key findings with URLs and publication dates."
                        ),
                    }],
                )
                self._last_claude_call = time.time()
                text = " ".join(
                    block.text for block in resp.content if hasattr(block, "text")
                ).strip()
                return {
                    "query": query,
                    "content": text or "",
                    "citations": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            except anthropic.RateLimitError:
                wait = 60 * attempt
                if attempt < max_retries:
                    log(f"  Rate limit — waiting {wait}s before retry {attempt}/{max_retries - 1}...")
                    time.sleep(wait)
                else:
                    log(f"  Rate limit: gave up after {max_retries} attempts.")
            except Exception as e:
                log(f"  Claude web_search error ({type(e).__name__}): {e}")
                break

        self._last_claude_call = time.time()
        return {
            "query": query,
            "content": "",
            "citations": [],
            "search_error": "rate_limit_or_error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def extract_json(text: str) -> dict | None:
    stripped = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    for pattern in [r"(\{.*\})", r"```json\s*(\{.*?\})\s*```"]:
        m = re.search(pattern, stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    return None
