"""
Search Agent
Sources: Perplexity API (primary), Claude web_search (fallback)
Focuses on: Apple, Qualcomm, MediaTek, Chinese OEMs, Samsung,
            Android, network operators, AI agents, 6G, CPE

Memory-aware: reads search.md before each run to avoid repetition,
writes findings back after each run. Builds knowledge graph after synthesis.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests


def log(msg: str) -> None:
    """Timestamped, unbuffered print for real-time GitHub Actions output."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


class SearchAgent:
    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "")
        self.base_topics = config["search"]["topics"]
        self._max_topics = 12
        # Delay between consecutive Claude API calls (seconds)
        # Today-only results are compact so 12 topics stay within rate limits
        self._claude_call_interval = 8

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def search_industry_news(self) -> dict:
        """
        Memory-aware search:
        1. Read search.md → determine what gaps/priorities to focus on
        2. Build topic list = gaps + base topics (prioritised)
        3. Search (Perplexity or Claude web_search only, no training data)
        4. Synthesise results
        5. Update search.md and knowledge_graph.json
        """
        from memory_manager import MemoryManager
        from knowledge_graph import KnowledgeGraph

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.perplexity_key:
            log(f"Search source: Perplexity (primary) — 12 topics, today only ({today})")
        else:
            log(f"Search source: Claude web_search — 12 topics, today only ({today})")

        memory = MemoryManager(self.config)
        kg = KnowledgeGraph(self.config)

        # Step 1: Read memory to guide this run
        log("Reading long-term memory (search.md)...")
        mem_state = memory.read()
        priorities = mem_state.get("next_priorities", [])
        confirmed = mem_state.get("confirmed_facts", [])
        gaps = mem_state.get("gaps", [])

        # Step 2: Build prioritised topic list
        topics = self._build_topic_list(priorities, gaps)
        log(f"Topics this run: {len(topics)} "
            f"({min(len(priorities)+len(gaps),5)} priority gaps + base topics)")
        if confirmed:
            log(f"Already confirmed: {len(confirmed)} facts — skipping repeats")

        # Step 3: Search
        raw_results = []
        for i, topic in enumerate(topics, 1):
            log(f"  [{i}/{len(topics)}] {topic[:70]}...")
            result = self._search(topic)
            ok = "✓" if result.get("content", "").strip() else "✗ empty"
            log(f"         → {ok}")
            raw_results.append(result)

        success_count = sum(1 for r in raw_results if r.get("content", "").strip())
        log(f"Search complete: {success_count}/{len(topics)} returned content")

        has_content = success_count > 0
        if not has_content:
            log("WARNING: All searches returned empty — PERPLEXITY_API_KEY not set and Claude rate-limited.")
            return {
                "summary": "⚠️ 搜尋未取得資料。請確認 PERPLEXITY_API_KEY 已設定於 GitHub Secrets。",
                "highlights": ["搜尋工具無法存取，請檢查 GitHub Secrets 中的 PERPLEXITY_API_KEY 設定"],
                "categories": {},
                "all_sources": [],
                "market_signals": [],
                "search_status": "failed",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Step 4: Synthesise
        log("Synthesising results...")
        skills_ctx = self._load_skills_context()
        confirmed_ctx = (
            "\n\nAlready confirmed facts (do NOT repeat these as highlights, focus on NEW findings):\n"
            + "\n".join(f"- {f}" for f in confirmed[:15])
            if confirmed else ""
        )
        result = self._synthesize(raw_results, skills_ctx + confirmed_ctx)

        # Step 5: Update memory and knowledge graph
        log("Updating long-term memory (search.md)...")
        memory.update(raw_results, result)
        log("Updating knowledge graph...")
        kg.update_from_synthesis(result)
        kg_stats = kg.get_stats()
        log(f"Knowledge graph: {kg_stats['nodes']} nodes, {kg_stats['edges']} edges")

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_topic_list(self, priorities: list[str], gaps: list[str]) -> list[str]:
        seen: set[str] = set()
        topics: list[str] = []
        for p in (priorities + gaps)[:5]:
            if p not in seen:
                topics.append(p)
                seen.add(p)
        # Then base topics up to the per-run cap
        for t in self.base_topics:
            if t not in seen and len(topics) < self._max_topics:
                topics.append(t)
                seen.add(t)
        return topics

    def _search(self, query: str) -> dict:
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
                        "You are a semiconductor industry analyst. Provide factual, "
                        "sourced information from credible media: official company blogs, "
                        "Reuters, Bloomberg, Nikkei, IEEE, The Verge, Ars Technica, "
                        "AnandTech, SemiAnalysis, Counterpoint Research, IDC. "
                        "Exclude personal blogs and unverified social media. "
                        "ONLY return news published today. Discard anything older."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"News published TODAY ({today}) about: {query}\n\n"
                        "IMPORTANT: Only include articles published on {today}. "
                        "Return JSON with keys: findings (list of str), "
                        "sources (list of {{title,url,date}}), significance (str)"
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
            log(f"         Perplexity failed ({type(e).__name__}), falling back to Claude")
            return None

    def _claude_search(self, query: str) -> dict:
        """Search via Claude web_search tool. Retries on rate limit with backoff."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
                            "Focus on credible sources only. Return key findings with URLs and publication dates."
                        ),
                    }],
                )
                text = " ".join(
                    block.text for block in resp.content if hasattr(block, "text")
                ).strip()
                # Pace consecutive Claude calls to stay within rate limits
                time.sleep(self._claude_call_interval)
                return {
                    "query": query,
                    "content": text if text else "",
                    "citations": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            except anthropic.RateLimitError:
                wait = 60 * attempt  # 60s, 120s, 180s
                if attempt < max_retries:
                    log(f"         Rate limit hit — waiting {wait}s before retry {attempt}/{max_retries-1}...")
                    time.sleep(wait)
                else:
                    log(f"         Rate limit: gave up after {max_retries} attempts. Skipping topic.")
            except Exception as e:
                log(f"         Claude web_search error ({type(e).__name__}): {e}")
                break
        return {
            "query": query,
            "content": "",
            "search_error": "rate_limit_or_error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _load_skills_context(self) -> str:
        path = Path(__file__).parent.parent / "skills" / "learned_skills.json"
        if not path.exists():
            return ""
        with open(path, encoding="utf-8") as f:
            skills = json.load(f).get("skills", [])
        if not skills:
            return ""
        snippets = [s["prompt_addition"] for s in skills[:8]]
        return "\n\nApply these learned analysis skills:\n" + "\n".join(
            f"- {s}" for s in snippets
        )

    def _synthesize(self, results: list[dict], skills_ctx: str) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prompt = f"""You are the VP of Product BU & Strategy Planning at a leading SOC company.
Mission: Develop the world's strongest Agentic Mobile & CPE SoC.
Success criteria: pricing power, market share growth, customer lock-in.

TODAY'S DATE: {today}
CRITICAL: Only synthesise articles published on {today}. Discard any content from earlier dates.

Synthesize the following search results into a structured industry dynamics report.

Search Results (JSON):
{json.dumps(results, indent=2, ensure_ascii=False)}
{skills_ctx}

Return ONLY raw JSON. No markdown. No ```json. No text before or after. Start with {{ end with }}:
{{
  "summary": "2-3 sentence executive summary in Traditional Chinese",
  "highlights": ["5 key highlights (Traditional Chinese)"],
  "categories": {{
    "apple":              {{"news": ["item1","item2"], "implications": "str"}},
    "qualcomm":          {{"news": ["item1","item2"], "implications": "str"}},
    "mediatek":          {{"news": ["item1","item2"], "implications": "str"}},
    "chinese_oems":      {{"news": ["item1","item2"], "implications": "str"}},
    "samsung":           {{"news": ["item1","item2"], "implications": "str"}},
    "android_ecosystem": {{"news": ["item1","item2"], "implications": "str"}},
    "network_operators": {{"news": ["item1","item2"], "implications": "str"}},
    "ai_agent_apps":     {{"news": ["item1","item2"], "implications": "str"}},
    "6g_technology":     {{"news": ["item1","item2"], "implications": "str"}},
    "cpe_devices":       {{"news": ["item1","item2"], "implications": "str"}}
  }},
  "all_sources": [
    {{"title": "", "url": "", "date": "", "credibility": "official|media|research"}}
  ],
  "market_signals": ["signal1", "signal2"],
  "generated_at": "{datetime.now(timezone.utc).isoformat()}"
}}"""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text
                result = self._extract_json(text)
                if result:
                    return result
                log(f"Synthesis: JSON parse failed (attempt {attempt}), raw length: {len(text)}")
            except anthropic.RateLimitError:
                wait = 60 * attempt
                if attempt < max_retries:
                    log(f"Synthesis rate limit — waiting {wait}s before retry {attempt}/{max_retries-1}...")
                    time.sleep(wait)
                else:
                    log("Synthesis rate limit: gave up after max retries.")
            except Exception as e:
                log(f"Synthesis error: {e}")
                break
        return {
            "summary": "搜尋資料已收集，分析合成失敗，請檢查 API key 設定。",
            "highlights": [],
            "categories": {},
            "all_sources": [],
            "market_signals": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_json(text: str) -> dict | None:
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
