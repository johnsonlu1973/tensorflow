"""
Memory Manager
Maintains soc-agent/data/search.md — the agent's long-term search memory.

Each search run:
  1. READ  → understand what was already found, what gaps remain, next priorities
  2. WRITE → record new findings, mark gaps filled, update next priorities

search.md structure (machine + human readable):
  - Coverage table: topic × depth × last_searched
  - Key findings (de-duplicated across runs)
  - Confirmed facts (appeared in ≥2 independent searches)
  - Gaps: topics / angles not yet covered
  - Next-run priorities (ranked list)
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import os


class MemoryManager:
    def __init__(self, config: dict):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.memory_path = Path(__file__).parent.parent / "data" / "search.md"
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self) -> dict:
        """Parse search.md and return structured memory dict."""
        if not self.memory_path.exists():
            return self._empty_memory()
        raw = self.memory_path.read_text(encoding="utf-8")
        return self._parse(raw)

    def update(self, new_results: list[dict], synthesized: dict) -> None:
        """Merge new search results into memory and rewrite search.md."""
        current = self.read()
        updated = self._merge(current, new_results, synthesized)
        self.memory_path.write_text(self._render(updated), encoding="utf-8")
        print(f"[Memory] search.md updated — {len(updated['findings'])} total findings, "
              f"{len(updated['gaps'])} gaps remaining")

    def get_next_priorities(self) -> list[str]:
        """Return the prioritised list of topics for the next search run."""
        mem = self.read()
        return mem.get("next_priorities", [])

    def get_confirmed_facts(self) -> list[str]:
        """Return facts confirmed across multiple search runs."""
        mem = self.read()
        return mem.get("confirmed_facts", [])

    # ------------------------------------------------------------------
    # Internal: parse / render markdown
    # ------------------------------------------------------------------

    def _parse(self, raw: str) -> dict:
        """Extract structured data from search.md using Claude."""
        if len(raw.strip()) < 100:
            return self._empty_memory()
        prompt = f"""Extract structured data from this search memory markdown file.
Return ONLY valid JSON:
{{
  "last_updated": "ISO timestamp or empty string",
  "coverage": [
    {{"topic": "", "depth": "low|medium|high", "last_searched": "", "summary": ""}}
  ],
  "findings": ["key finding 1", "key finding 2"],
  "confirmed_facts": ["fact confirmed in multiple runs"],
  "gaps": ["topic or angle not yet covered"],
  "repeated_info": ["information appearing multiple times"],
  "next_priorities": ["highest priority topic for next run", "second priority"]
}}

Search memory content:
{raw[:6000]}"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"[Memory] parse error: {e}")
        return self._empty_memory()

    def _merge(self, current: dict, new_results: list[dict], synthesized: dict) -> dict:
        """Ask Claude to merge new findings into current memory."""
        now = datetime.now(timezone.utc).isoformat()
        categories = synthesized.get("categories", {})
        sources = synthesized.get("all_sources", [])

        prompt = f"""You are the memory system for a SOC strategy intelligence agent.

CURRENT MEMORY STATE:
{json.dumps(current, ensure_ascii=False, indent=2)}

NEW SEARCH RESULTS (this run):
Categories found: {json.dumps(list(categories.keys()), ensure_ascii=False)}
Summary: {synthesized.get('summary', '')}
Market signals: {json.dumps(synthesized.get('market_signals', []), ensure_ascii=False)}
Sources: {len(sources)} sources retrieved
Raw results count: {len(new_results)}

NEW FINDINGS (per category):
{json.dumps({k: v.get('news', [])[:3] for k, v in categories.items()}, ensure_ascii=False, indent=2)}

TASK: Produce an UPDATED memory state by:
1. Adding genuinely NEW findings (not already in current memory)
2. Moving findings that appear AGAIN into confirmed_facts
3. Removing gaps that are now covered
4. Adding NEW gaps discovered from this run
5. Re-ranking next_priorities based on what's still missing
6. Updating coverage table with depth assessment

Topics we track: Apple, Qualcomm, MediaTek, Chinese OEMs, Samsung, Android ecosystem,
Network operators, AI agent apps, 6G technology, CPE devices.

Return ONLY valid JSON with this structure:
{{
  "last_updated": "{now}",
  "coverage": [
    {{"topic": "Apple", "depth": "low|medium|high", "last_searched": "{now}", "summary": "1-sentence summary"}},
    {{"topic": "Qualcomm", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "MediaTek", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "Chinese OEMs", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "Samsung", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "Android Ecosystem", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "Network Operators", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "AI Agent Apps", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "6G Technology", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}},
    {{"topic": "CPE Devices", "depth": "low|medium|high", "last_searched": "{now}", "summary": ""}}
  ],
  "findings": ["max 40 unique key findings, most recent first"],
  "confirmed_facts": ["facts confirmed in 2+ runs"],
  "gaps": ["specific topics/angles still not covered"],
  "repeated_info": ["info seen repeatedly — confirmed signal"],
  "next_priorities": ["top 5 topics ranked by gap importance for SOC strategy"]
}}"""

        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"[Memory] merge error: {e}")
        return current

    def _render(self, mem: dict) -> str:
        """Render memory dict back to human-readable markdown."""
        now_str = mem.get("last_updated", datetime.now(timezone.utc).isoformat())
        lines = [
            "# SOC Strategy Agent — Search Memory",
            "",
            f"> **Last Updated:** {now_str}",
            f"> **Total Findings:** {len(mem.get('findings', []))} | "
            f"**Confirmed Facts:** {len(mem.get('confirmed_facts', []))} | "
            f"**Open Gaps:** {len(mem.get('gaps', []))}",
            "",
            "---",
            "",
            "## 📊 Search Coverage",
            "",
            "| Topic | Depth | Last Searched | Summary |",
            "|-------|-------|--------------|---------|",
        ]
        depth_icon = {"high": "🟢", "medium": "🟡", "low": "🔴", "": "⬜"}
        for c in mem.get("coverage", []):
            icon = depth_icon.get(c.get("depth", ""), "⬜")
            ts = c.get("last_searched", "")[:10]
            lines.append(
                f"| {c.get('topic','')} | {icon} {c.get('depth','').capitalize()} "
                f"| {ts} | {c.get('summary','')[:80]} |"
            )

        lines += [
            "",
            "---",
            "",
            "## 🔑 Key Findings (de-duplicated)",
            "",
        ]
        for i, f in enumerate(mem.get("findings", [])[:40], 1):
            lines.append(f"{i}. {f}")

        lines += [
            "",
            "---",
            "",
            "## ✅ Confirmed Facts (appeared in 2+ runs)",
            "",
        ]
        for f in mem.get("confirmed_facts", []):
            lines.append(f"- {f}")

        lines += [
            "",
            "---",
            "",
            "## ⚠️ Information Gaps (not yet covered)",
            "",
        ]
        for g in mem.get("gaps", []):
            lines.append(f"- [ ] {g}")

        lines += [
            "",
            "---",
            "",
            "## 🔄 Repeated / High-Confidence Signals",
            "",
        ]
        for r in mem.get("repeated_info", []):
            lines.append(f"- {r}")

        lines += [
            "",
            "---",
            "",
            "## 🎯 Next Search Priorities",
            "",
            "> The next search run will focus on these topics first.",
            "",
        ]
        for i, p in enumerate(mem.get("next_priorities", [])[:5], 1):
            lines.append(f"{i}. {p}")

        return "\n".join(lines) + "\n"

    def _empty_memory(self) -> dict:
        return {
            "last_updated": "",
            "coverage": [],
            "findings": [],
            "confirmed_facts": [],
            "gaps": [
                "Qualcomm CPE chipset (X Elite / X Plus) AI roadmap",
                "MediaTek CPE-specific AI features (Filogic series)",
                "6G standardisation timeline (ITU-R IMT-2030, 3GPP Rel-20)",
                "Chinese OEM AI agent integration (Xiaomi HyperAI, OPPO AndesGPT)",
                "Network operator AI-native network plans (T-Mobile, SKT, KDDI)",
                "Killer app / super app AI agent monetisation models",
                "On-device privacy regulations impact on AI SoC design",
                "Samsung Exynos 2600 AI NPU strategy vs SD / MediaTek",
                "Apple A19 / M-series AI SoC roadmap signals",
                "CPE Wi-Fi 7 + AI gateway use cases (ISP bundling)",
            ],
            "repeated_info": [],
            "next_priorities": [
                "6G standardisation and timeline (biggest gap for 2-year outlook)",
                "CPE AI SoC competitive landscape (Qualcomm vs MediaTek vs Broadcom)",
                "Chinese OEM AI agent feature differentiation",
                "Network operator AI-native plans and SoC requirements",
                "Killer app / super app AI agent integration with SoC",
            ],
        }
