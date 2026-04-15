"""
Knowledge Graph
Stores a relational graph in soc-agent/data/knowledge_graph.json.

Node types:
  company       Apple, Qualcomm, MediaTek, Samsung, Xiaomi ...
  chip          Snapdragon 8 Elite Gen2, Dimensity 9500 ...
  technology    on-device LLM, NPU, 6G, Wi-Fi 7 ...
  use_case      voice agent offline, 4K AI video generation ...
  pain_point    high power consumption, latency >200ms ...
  app           Gemini, Siri, HyperAI ...
  operator      T-Mobile, SKT, KDDI ...
  strategy      customer lock-in via SDK, pricing power via NPU perf ...

Edge types / relations:
  develops, supports, enables, blocks, competes_with,
  requires, leads_to, addresses, predicts_2y

Usage:
  - After each search: update_from_synthesis(synthesized_data)
  - In use-case report: predict_future_use_cases(current_use_cases)
  - In strategy report: link_strategy_to_use_cases(strategy)
  - Gap detection:      get_under_explored_nodes()
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic


class KnowledgeGraph:
    def __init__(self, config: dict):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.graph_path = Path(__file__).parent.parent / "data" / "knowledge_graph.json"
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        self._graph: dict = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_from_synthesis(self, synthesized: dict) -> None:
        """Extract entities and relations from a synthesized search result."""
        prompt = f"""Extract entities and relationships from this industry analysis for a knowledge graph.

Analysis data:
{json.dumps(synthesized, ensure_ascii=False, indent=2)[:5000]}

Return ONLY valid JSON:
{{
  "nodes": [
    {{
      "id": "unique_snake_case_id",
      "type": "company|chip|technology|use_case|pain_point|app|operator|strategy",
      "label": "human readable name",
      "properties": {{"detail": "any key facts"}}
    }}
  ],
  "edges": [
    {{
      "from": "node_id",
      "to": "node_id",
      "relation": "develops|supports|enables|blocks|competes_with|requires|leads_to|addresses",
      "strength": 0.9,
      "evidence": "brief reason"
    }}
  ]
}}

Focus on: chips, companies, technologies, use cases, pain points.
Extract 10-20 nodes and 15-30 edges. Be specific (e.g. 'snapdragon_8_elite_gen2', not 'qualcomm_chip').
"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return
            extracted = json.loads(m.group())
            self._merge_into_graph(extracted)
            self._save()
            print(f"[KG] Updated: {len(self._graph['nodes'])} nodes, {len(self._graph['edges'])} edges")
        except Exception as e:
            print(f"[KG] update error: {e}")

    def predict_future_use_cases(self, current_use_cases: list[str]) -> list[dict]:
        """
        Use graph paths + trend velocity to predict 2-year future use cases.
        Looks for: technology trends → emerging use cases, confirmed signals → extrapolation.
        """
        graph_summary = self._summarize_for_prompt()
        prompt = f"""You are a SoC industry strategist predicting 2-year future use cases.

Current use cases identified:
{json.dumps(current_use_cases, ensure_ascii=False, indent=2)}

Knowledge graph (entities and relations discovered from real search data):
{graph_summary}

Based on the GRAPH PATHS and trend velocity (how many times a technology/use case has appeared),
predict use cases that will emerge within 2 years. Focus on:
1. Technologies that currently "support" use cases but at low adoption → will mature
2. Pain points that multiple companies are racing to address → solution imminent
3. "leads_to" chains: A enables B, B enables C → predict C becoming mainstream
4. Gaps where NO company has yet addressed a critical need → opportunity

Return ONLY valid JSON:
{{
  "predictions": [
    {{
      "use_case": "specific use case name",
      "description": "what users/OEMs will be able to do",
      "driving_forces": ["technology or trend driving this"],
      "graph_path": "node_a -> relation -> node_b -> relation -> this_use_case",
      "confidence": 0.85,
      "timeline_months": 18,
      "pain_point_addressed": "what current pain this solves",
      "chip_requirement": "what the SoC must support to enable this"
    }}
  ]
}}
Predict 5-8 use cases. Only use evidence from the graph, not speculation.
"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group()).get("predictions", [])
        except Exception as e:
            print(f"[KG] predict error: {e}")
            print(f"[KG] stop_reason: {resp.stop_reason}")          # ← 加這行
            print(f"[KG] response length: {len(text)}")             # ← 加這行
            print(f"[KG] response tail:\n{text[-200:]}")            # ← 加這行
        return []

    def link_strategy_to_use_cases(self, strategy_items: list[dict]) -> list[dict]:
        """
        For each strategy recommendation, find ALL related use cases and pain points
        in the graph, not just the ones it was designed for.
        Makes strategy recommendations more complete.
        """
        if not strategy_items:
            return []
        graph_summary = self._summarize_for_prompt()
        prompt = f"""Given these strategy recommendations and the knowledge graph,
find ALL use cases and pain points each strategy addresses (not just the primary ones).
This ensures strategies are presented with full coverage, not just specific use cases.

Strategies:
{json.dumps(strategy_items, ensure_ascii=False, indent=2)[:3000]}

Knowledge graph:
{graph_summary}

Return ONLY valid JSON:
{{
  "enriched_strategies": [
    {{
      "title": "strategy title",
      "primary_use_cases": ["directly targeted"],
      "secondary_use_cases": ["also addressed via graph connections"],
      "pain_points_solved": ["all pain points, direct and indirect"],
      "ecosystem_connections": ["companies/apps/operators that benefit"],
      "success_criteria_evidence": ["pricing_power|market_share|customer_lock_in with graph evidence"]
    }}
  ]
}}"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group()).get("enriched_strategies", [])
        except Exception as e:
            print(f"[KG] link error: {e}")
        return strategy_items

    def get_under_explored_nodes(self) -> list[str]:
        """Return nodes with few edges — signals for next search priorities."""
        node_edge_count: dict[str, int] = {}
        for node_id in self._graph.get("nodes", {}):
            node_edge_count[node_id] = 0
        for edge in self._graph.get("edges", []):
            node_edge_count[edge["from"]] = node_edge_count.get(edge["from"], 0) + 1
            node_edge_count[edge["to"]] = node_edge_count.get(edge["to"], 0) + 1

        sparse = [
            self._graph["nodes"][nid].get("label", nid)
            for nid, cnt in node_edge_count.items()
            if cnt <= 2
        ]
        return sparse[:10]

    def get_stats(self) -> dict:
        return {
            "nodes": len(self._graph.get("nodes", {})),
            "edges": len(self._graph.get("edges", [])),
            "last_updated": self._graph.get("last_updated", ""),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _merge_into_graph(self, extracted: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._graph.setdefault("nodes", {})
        self._graph.setdefault("edges", [])
        self._graph["last_updated"] = now

        for node in extracted.get("nodes", []):
            nid = node.get("id", "")
            if not nid:
                continue
            if nid in self._graph["nodes"]:
                # Update existing node: increment seen_count
                existing = self._graph["nodes"][nid]
                existing["seen_count"] = existing.get("seen_count", 1) + 1
                existing["last_seen"] = now
                # Merge properties
                existing.setdefault("properties", {}).update(node.get("properties", {}))
            else:
                self._graph["nodes"][nid] = {
                    "type": node.get("type", ""),
                    "label": node.get("label", nid),
                    "properties": node.get("properties", {}),
                    "first_seen": now,
                    "last_seen": now,
                    "seen_count": 1,
                }

        for edge in extracted.get("edges", []):
            # Avoid exact duplicate edges
            duplicate = any(
                e["from"] == edge["from"]
                and e["to"] == edge["to"]
                and e["relation"] == edge["relation"]
                for e in self._graph["edges"]
            )
            if not duplicate:
                edge["added_at"] = now
                self._graph["edges"].append(edge)
            else:
                # Strengthen existing edge
                for e in self._graph["edges"]:
                    if (e["from"] == edge["from"] and e["to"] == edge["to"]
                            and e["relation"] == edge["relation"]):
                        e["strength"] = min(1.0, e.get("strength", 0.5) + 0.1)
                        e["confirmed_count"] = e.get("confirmed_count", 1) + 1
                        break

    def _summarize_for_prompt(self) -> str:
        """Compact graph representation for prompt context."""
        nodes = self._graph.get("nodes", {})
        edges = self._graph.get("edges", [])
        lines = [f"Graph: {len(nodes)} nodes, {len(edges)} edges"]

        # High-confidence edges (strength > 0.7 or confirmed multiple times)
        strong_edges = [
            e for e in edges
            if e.get("strength", 0) >= 0.7 or e.get("confirmed_count", 1) > 1
        ]
        lines.append(f"\nStrong relations ({len(strong_edges)}):")
        for e in strong_edges[:30]:
            f_label = nodes.get(e["from"], {}).get("label", e["from"])
            t_label = nodes.get(e["to"], {}).get("label", e["to"])
            lines.append(f"  {f_label} --[{e['relation']}]--> {t_label} "
                         f"(str={e.get('strength',0):.1f})")

        # High seen_count nodes (confirmed entities)
        hot_nodes = sorted(
            [(nid, n) for nid, n in nodes.items()],
            key=lambda x: x[1].get("seen_count", 1),
            reverse=True,
        )[:15]
        lines.append(f"\nFrequently seen entities:")
        for nid, n in hot_nodes:
            lines.append(f"  [{n.get('type','')}] {n.get('label', nid)} "
                         f"(seen {n.get('seen_count',1)}x)")
        return "\n".join(lines)

    def _load(self) -> dict:
        if self.graph_path.exists():
            try:
                with open(self.graph_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"nodes": {}, "edges": [], "last_updated": "", "version": "1.0"}

    def _save(self) -> None:
        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(self._graph, f, ensure_ascii=False, indent=2)
