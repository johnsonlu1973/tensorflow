"""Core SOC Planning Agent using Claude API with web search."""
import json
from datetime import datetime
from typing import Optional

import anthropic

from config import MODEL, DAILY_TOPICS, WEEKLY_THEMES, SEARCH_QUERIES
from database import Database


SYSTEM_PROMPT = """You are an expert SOC (System-on-Chip) product planning strategist specializing in telecom and wireless SoC design.

Your expertise covers:
- 3GPP standards (Release 15~20, 5G-Advanced, 6G research)
- Baseband processor and modem SoC architecture
- AI/ML acceleration in mobile and infrastructure chipsets
- Competitive landscape: Qualcomm, MediaTek, Samsung, Apple, Intel, Marvell, Broadcom
- Open RAN, vRAN, and edge computing hardware requirements
- Market trends: on-device AI inference, mmWave, massive MIMO, network slicing

Your role is to:
1. COLLECT: Search and gather the latest information on 3GPP standards, market trends, and competitor activities
2. ANALYZE: Cross-reference data to identify product gaps, opportunities, and risks
3. RECOMMEND: Provide concrete product planning recommendations with priority and timeline
4. LEARN: Incorporate user feedback to improve analysis quality over time

When collecting data, always cite sources. When analyzing, connect multiple data points.
When you don't know something, say so rather than hallucinating specifications.
"""


def _build_learning_context(db: Database) -> str:
    """Build context from past feedback to help Claude improve."""
    prefs = db.get_all_preferences()
    recent_feedback = db.get_all_feedback()[-20:]  # last 20 feedback items

    context_parts = []

    if prefs:
        context_parts.append("=== User Preferences & Focus Areas ===")
        for k, v in prefs.items():
            context_parts.append(f"- {k}: {v}")

    if recent_feedback:
        context_parts.append("\n=== Recent User Feedback (for learning) ===")
        for fb in recent_feedback[-10:]:
            context_parts.append(
                f"- [{fb['target_type']} #{fb['target_id']}] {fb['comment']}"
            )

    return "\n".join(context_parts) if context_parts else ""


def _extract_sources(content: list) -> list:
    """Extract web search result URLs from content blocks."""
    sources = []
    for block in content:
        if hasattr(block, "type") and block.type == "tool_result":
            pass
        if isinstance(block, dict) and block.get("type") == "web_search_tool_result":
            for result in block.get("content", []):
                if isinstance(result, dict) and result.get("url"):
                    sources.append(result["url"])
    return list(set(sources))


class SOCPlanningAgent:
    def __init__(self, db: Database, api_key: str):
        self.db = db
        self.client = anthropic.Anthropic(api_key=api_key)
        self.tools = [
            {"type": "web_search_20260209", "name": "web_search"},
            {"type": "web_fetch_20260209", "name": "web_fetch"},
        ]

    def _run_with_search(self, user_message: str, extra_context: str = "") -> tuple[str, list]:
        """Run Claude with web search tools, return (text_response, sources)."""
        messages = [{"role": "user", "content": user_message}]

        system = SYSTEM_PROMPT
        if extra_context:
            system += f"\n\n{extra_context}"

        all_content = []
        sources = []
        max_iterations = 8  # prevent infinite loops

        for _ in range(max_iterations):
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=8192,
                thinking={"type": "adaptive"},
                system=system,
                tools=self.tools,
                messages=messages,
            ) as stream:
                response = stream.get_final_message()

            # Collect sources from web search results
            for block in response.content:
                if hasattr(block, "type"):
                    if block.type == "web_search_tool_result":
                        for item in getattr(block, "content", []):
                            if hasattr(item, "url") and item.url:
                                sources.append(item.url)
                    all_content.append(block)

            if response.stop_reason in ("end_turn", "max_tokens"):
                break

            if response.stop_reason == "tool_use":
                # Add assistant response to messages and continue loop
                messages.append({"role": "assistant", "content": response.content})
                # The tool results are automatically handled server-side
                # But we need to check if there are pending tool calls
                tool_uses = [b for b in response.content if hasattr(b, "type") and b.type == "server_tool_use"]
                if not tool_uses:
                    break
                # Tool results from server are included in next response automatically
                # We need to add a continuation message
                messages.append({
                    "role": "user",
                    "content": "Please continue with the search results and complete your analysis."
                })
            else:
                break

        # Extract final text
        text_blocks = [
            b.text for b in response.content
            if hasattr(b, "type") and b.type == "text" and hasattr(b, "text")
        ]
        final_text = "\n\n".join(text_blocks)
        return final_text, list(set(sources))

    def collect_daily_updates(self) -> list[int]:
        """Run daily data collection across all topics. Returns list of saved collection IDs."""
        collection_ids = []
        learning_ctx = _build_learning_context(self.db)

        for category, queries in SEARCH_QUERIES.items():
            for query in queries:
                prompt = f"""Search for the latest information on: **{query}**

Please:
1. Search for recent news and announcements (focus on last 3-6 months)
2. Extract key facts, specifications, and strategic implications
3. Note any 3GPP standards updates, product launches, or market shifts
4. Highlight what this means for SoC product planning

Provide a structured summary with key findings and their product planning implications."""

                if learning_ctx:
                    prompt += f"\n\nContext from previous interactions:\n{learning_ctx}"

                text, sources = self._run_with_search(prompt)

                if text.strip():
                    coll_id = self.db.save_collection(
                        category=category,
                        topic=query,
                        content=text,
                        sources=sources,
                    )
                    collection_ids.append(coll_id)

        return collection_ids

    def run_weekly_analysis(self) -> int:
        """Run comprehensive weekly cross-analysis. Returns analysis ID."""
        # Get recent collections for context
        recent = self.db.get_recent_collections(days=7)
        learning_ctx = _build_learning_context(self.db)
        recent_feedback = self.db.get_all_feedback()

        # Build collection summaries
        collection_summary = ""
        collection_ids = []
        for item in recent[:20]:  # limit context size
            collection_ids.append(item["id"])
            collection_summary += f"\n\n### [{item['category'].upper()}] {item['topic']}\n{item['content'][:800]}..."

        # Build feedback context
        feedback_context = ""
        if recent_feedback:
            feedback_context = "\n\nUser feedback on previous analyses:\n"
            for fb in recent_feedback[-15:]:
                feedback_context += f"- {fb['comment']}\n"

        prompt = f"""Based on the market intelligence collected this week, conduct a comprehensive SOC product planning analysis.

## This Week's Intelligence Gathered:
{collection_summary}

## Analysis Framework:
1. **3GPP Standards Alignment**: Which upcoming standard features require new SoC capabilities?
2. **Competitive Gap Analysis**: Where are competitors leading vs. lagging?
3. **AI/ML Integration Opportunities**: What AI features are becoming table-stakes?
4. **Market Timing**: What's the urgency for each product decision?
5. **Prioritized Recommendations**: Top 5 product planning actions with rationale

Please also search for any breaking news this week that supplements the collected data.

{feedback_context}

Format the analysis as an executive-level product planning brief with clear sections,
specific technical recommendations, and market timing guidance."""

        if learning_ctx:
            prompt += f"\n\n{learning_ctx}"

        text, sources = self._run_with_search(prompt)

        analysis_id = self.db.save_analysis(
            analysis_type="weekly",
            title=f"Weekly SOC Product Planning Brief — {datetime.now().strftime('%Y-W%U')}",
            content=text,
            collection_ids=collection_ids,
        )

        # Extract and save product insights
        self._extract_insights_from_analysis(text, analysis_id)

        return analysis_id

    def _extract_insights_from_analysis(self, analysis_text: str, analysis_id: int):
        """Extract actionable insights from analysis and save them."""
        prompt = f"""From this SOC product planning analysis, extract the top actionable insights.

Analysis:
{analysis_text[:3000]}

For each insight, provide:
- type: one of [feature_gap, competitive_threat, market_opportunity, standards_requirement]
- title: short title (max 80 chars)
- content: detailed description
- priority: high/medium/low

Return as JSON array: [{{"type": ..., "title": ..., "content": ..., "priority": ...}}]
Return ONLY the JSON, no other text."""

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            text = response.content[0].text.strip()
            # Handle markdown code fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            insights = json.loads(text)
            for insight in insights[:10]:
                self.db.save_insight(
                    insight_type=insight.get("type", "general"),
                    title=insight.get("title", "Untitled"),
                    content=insight.get("content", ""),
                    priority=insight.get("priority", "medium"),
                )
        except (json.JSONDecodeError, IndexError, KeyError):
            pass  # insight extraction is best-effort

    def ask_question(self, question: str) -> str:
        """Answer an ad-hoc product planning question with search."""
        # Add recent context
        recent_analyses = self.db.get_recent_analyses(days=30)
        context_parts = [_build_learning_context(self.db)]

        if recent_analyses:
            context_parts.append("Recent analysis context:")
            for a in recent_analyses[:3]:
                context_parts.append(f"[{a['analysis_type']}] {a['title']}: {a['content'][:500]}...")

        extra_context = "\n\n".join(filter(None, context_parts))

        text, sources = self._run_with_search(question, extra_context)

        if sources:
            text += "\n\n**Sources:** " + ", ".join(sources[:5])

        return text

    def update_preferences(self, preferences: dict):
        """Save user preferences to improve future analyses."""
        for key, value in preferences.items():
            self.db.set_preference(key, str(value))

    def learn_from_feedback(self, target_type: str, target_id: int, comment: str, tags: list = None) -> int:
        """Save user feedback and update agent behavior."""
        fb_id = self.db.save_feedback(target_type, target_id, comment, tags or [])

        # Extract preference updates from feedback using Claude
        prompt = f"""A user provided feedback on a SOC product planning {target_type}:

"{comment}"

Extract any implicit preferences or focus areas from this feedback.
Return JSON: {{"preferences": {{"key": "value", ...}}}}
Keys should be descriptive like "preferred_depth", "focus_companies", "analysis_style".
Return ONLY the JSON, empty preferences if none found."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            for k, v in data.get("preferences", {}).items():
                self.db.set_preference(k, str(v))
        except (json.JSONDecodeError, IndexError):
            pass

        return fb_id
