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
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests


class SearchAgent:
    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "")
        self.base_topics = config["search"]["topics"]

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

        memory = MemoryManager(self.config)
        kg = KnowledgeGraph(self.config)

        # Step 1: Read memory to guide this run
        mem_state = memory.read()
        priorities = mem_state.get("next_priorities", [])
        confirmed = mem_state.get("confirmed_facts", [])
        gaps = mem_state.get("gaps", [])

        # Step 2: Build prioritised topic list
        # Put gap-filling topics first, then base topics
        topics = self._build_topic_list(priorities, gaps)
        print(f"[Search] This run: {len(topics)} topics "
              f"({len(priorities)} priority gaps + base topics)")
        if confirmed:
            print(f"[Search] Already confirmed in memory: {len(confirmed)} facts — will skip repeating")

        # Step 3: Search
        raw_results = []
        for topic in topics:
            print(f"  Searching: {topic[:70]}...")
            raw_results.append(self._search(topic))

        has_content = any(r.get("content", "").strip() for r in raw_results)
        if not has_content:
            print("WARNING: All searches returned empty — check PERPLEXITY_API_KEY.")
            return {
                "summary": "⚠️ 搜尋未取得資料。請確認 PERPLEXITY_API_KEY 已設定。",
                "highlights": ["搜尋工具無法存取，請檢查 GitHub Secrets 中的 PERPLEXITY_API_KEY 設定"],
                "categories": {},
                "all_sources": [],
                "market_signals": [],
                "search_status": "failed",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Step 4: Synthesise (pass confirmed facts so Claude knows what NOT to repeat)
        skills_ctx = self._load_skills_context()
        confirmed_ctx = (
            "\n\nAlready confirmed facts (do NOT repeat these as highlights, focus on NEW findings):\n"
            + "\n".join(f"- {f}" for f in confirmed[:15])
            if confirmed else ""
        )
        result = self._synthesize(raw_results, skills_ctx + confirmed_ctx)

        # Step 5: Update memory and knowledge graph
        memory.update(raw_results, result)
        kg.update_from_synthesis(result)
        kg_stats = kg.get_stats()
        print(f"[KG] Graph now has {kg_stats['nodes']} nodes, {kg_stats['edges']} edges")

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_topic_list(self, priorities: list[str], gaps: list[str]) -> list[str]:
        """
        Merge priority gaps with base topics.
        Gaps / priorities go first; base topics fill remaining slots.
        Max 12 topics per run to keep cost reasonable.
        """
        seen: set[str] = set()
        topics: list[str] = []
        # Priority gaps first
        for p in (priorities + gaps)[:5]:
            if p not in seen:
                topics.append(p)
                seen.add(p)
        # Then base topics
        for t in self.base_topics:
            if t not in seen and len(topics) < 12:
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
                        "Exclude personal blogs and unverified social media."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Latest news (past week) about: {query}\n\n"
                        "Return JSON with keys: findings (list of str), "
                        "sources (list of {title,url,date}), significance (str)"
                    ),
                },
            ],
            "return_citations": True,
            "search_recency_filter": "week",
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
            print(f"  Perplexity failed ({e}), falling back to Claude")
            return None

    def _claude_search(self, query: str) -> dict:
        """Search via Claude web_search tool. Returns empty content if unavailable."""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                messages=[{
                    "role": "user",
                    "content": (
                        f"Search for latest news (past week) about: {query}. "
                        "Focus on credible sources only. Return key findings with URLs."
                    ),
                }],
            )
            text = " ".join(
                block.text for block in resp.content if hasattr(block, "text")
            ).strip()
            return {
                "query": query,
                "content": text if text else "",
                "citations": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            print(f"  Claude web_search unavailable ({type(e).__name__}): {e}")
            return {
                "query": query,
                "content": "",
                "search_error": str(e),
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
        prompt = f"""You are the VP of Product BU & Strategy Planning at a leading SOC company.
Mission: Develop the world's strongest Agentic Mobile & CPE SoC.
Success criteria: pricing power, market share growth, customer lock-in.

Synthesize the following search results into a structured industry dynamics report.

Search Results (JSON):
{json.dumps(results, indent=2, ensure_ascii=False)}
{skills_ctx}

Return ONLY valid JSON with this exact structure:
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
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
             # ── 新增診斷 print ────────────────────────────── 
            print("=== RAW SYNTHESIS (first 500 chars) ===")
            print(text[:500])
            print("=== END RAW ===")
        # ──────────────────────────────────────────────
            result = self._extract_json(text)
            if result:
                return result
            print("Synthesis: JSON parse failed, raw text length:", len(text))
        except Exception as e:
            print(f"Synthesis error: {e}")
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
        """Robustly extract JSON from Claude responses (handles markdown code blocks)."""
        # 1. Try stripping markdown code fences
        stripped = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        # 2. Try to find the outermost JSON object
        for pattern in [
            r"(\{.*\})",          # standard
            r"```json\s*(\{.*?\})\s*```",  # fenced
        ]:
            m = re.search(pattern, stripped, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        # 3. Try the whole stripped text
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
        return None
