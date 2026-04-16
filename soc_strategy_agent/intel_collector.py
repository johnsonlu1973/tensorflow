"""
Agent 1: Intel Collector
Collects TODAY-only mobile/SoC/6G industry intelligence via 9 search queries,
then synthesises into IntelReport using Claude claude-opus-4-7.
"""
import json
from datetime import datetime, timezone

import anthropic

from config import ANTHROPIC_API_KEY, INTEL_MODEL, SYNTHESIS_MAX_TOKENS
from models import IntelItem, IntelReport
from web_search import WebSearch, extract_json, log

SYSTEM_PROMPT = """你是一家手機 SOC 公司的手機 SOC + CPE SOC BU VP 兼策略 VP。
你的任務是每天早上收集今天最新的行業情報，為當天的策略決策做準備。

規則：
- 只使用今天的資訊（已透過 search_recency_filter: "day" 過濾）
- 只引用有公信力的來源：Reuters、Bloomberg、Nikkei、The Verge、IEEE、TechCrunch、
  官方公司網站（qualcomm.com、mediatek.com、apple.com、samsung.com）、
  分析機構（Counterpoint Research、IDC、SemiAnalysis）
- 不使用個人部落格、無編輯團隊的媒體
- 不捏造數據，數字必須來自搜尋結果
- 不確定時標記「待確認」
- 每個 item 的 published_date 盡量填入今天日期（若搜尋結果有的話）"""

# 9 search queries covering all required categories
SEARCH_QUERIES: list[tuple[str, str]] = [
    (
        "Qualcomm MediaTek Apple mobile AI agent NPU chip announcement today",
        "competitor_dynamics",
    ),
    (
        "Xiaomi OPPO vivo Huawei Samsung AI phone launch feature today",
        "oem_moves",
    ),
    (
        "Google Android Gemini AI agent mobile update release today",
        "ecosystem_updates",
    ),
    (
        "mobile operator T-Mobile Verizon AT&T SK Telecom NTT DoCoMo 5G AI network today",
        "operator_dynamics",
    ),
    (
        "killer app super app AI agent mobile integration launch today",
        "app_trends",
    ),
    (
        "CPE home router WiFi7 AI gateway edge AI device announcement today",
        "cpe_updates",
    ),
    (
        "6G IMT-2030 3GPP Release-20 standard research spectrum announcement today",
        "tech_6g",
    ),
    (
        "Apple Qualcomm MediaTek Samsung 6G chip research standard collaboration today",
        "chip_6g_moves",
    ),
    (
        "mobile semiconductor chip acquisition investment partnership deal today",
        "industry_structure",
    ),
]

OUTPUT_SCHEMA = """
{
  "competitor_dynamics": [
    {"company": "str", "event_type": "str", "title": "str", "summary": "str",
     "impact_assessment": "str", "source_url": "str", "source_name": "str", "published_date": "str"}
  ],
  "oem_moves": [...same structure...],
  "ecosystem_updates": [...same structure...],
  "operator_dynamics": [...same structure...],
  "app_trends": [...same structure...],
  "cpe_updates": [...same structure...],
  "tech_6g": [...same structure...],
  "chip_6g_moves": [...same structure...],
  "industry_structure": [...same structure...]
}
"""


class IntelCollector:
    def __init__(self) -> None:
        self.searcher = WebSearch()
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def run(self) -> IntelReport:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        topic = f"daily_intel_{today.replace('-', '')}"
        log(f"[Agent 1] Starting intel collection for {today}")

        # Step 1: Run all 9 search queries
        raw_results: list[dict] = []
        all_sources: list[str] = []
        queries_used: list[str] = []

        for i, (query, category) in enumerate(SEARCH_QUERIES, 1):
            log(f"  [{i}/9] Searching: {query[:60]}...")
            result = self.searcher.search(query)
            result["category"] = category
            raw_results.append(result)
            queries_used.append(query)
            # Collect Perplexity citations
            for citation in result.get("citations", []):
                if isinstance(citation, str) and citation not in all_sources:
                    all_sources.append(citation)
                elif isinstance(citation, dict) and citation.get("url"):
                    url = citation["url"]
                    if url not in all_sources:
                        all_sources.append(url)

        # Step 2: Synthesise with Claude claude-opus-4-7
        log("[Agent 1] Synthesising with Claude claude-opus-4-7...")
        intel_data = self._synthesise(raw_results, today)

        # Step 3: Build IntelReport
        report = IntelReport(
            topic=topic,
            generated_at=datetime.now(timezone.utc),
            all_sources=all_sources,
            search_queries_used=queries_used,
        )

        field_map = {
            "competitor_dynamics": report.competitor_dynamics,
            "oem_moves": report.oem_moves,
            "ecosystem_updates": report.ecosystem_updates,
            "operator_dynamics": report.operator_dynamics,
            "app_trends": report.app_trends,
            "cpe_updates": report.cpe_updates,
            "tech_6g": report.tech_6g,
            "chip_6g_moves": report.chip_6g_moves,
            "industry_structure": report.industry_structure,
        }

        for field_name, field_list in field_map.items():
            for raw in intel_data.get(field_name, []):
                try:
                    field_list.append(IntelItem(**raw))
                except Exception:
                    pass

        # Collect any extra sources mentioned in synthesis output
        for field_name in field_map:
            for item in intel_data.get(field_name, []):
                url = item.get("source_url", "")
                if url and url not in report.all_sources:
                    report.all_sources.append(url)

        log(f"[Agent 1] Done. Collected {self._total_items(report)} intel items across {len(field_map)} categories.")
        return report

    def _synthesise(self, raw_results: list[dict], today: str) -> dict:
        search_block = "\n\n".join(
            f"=== Category: {r['category']} | Query: {r['query']} ===\n{r['content']}"
            for r in raw_results
            if r.get("content")
        )

        user_msg = f"""以下是今天（{today}）透過 9 個搜尋查詢收集到的行業資訊。
請將這些資訊整理成結構化的 Intel Report。

搜尋結果：
{search_block}

請嚴格按照以下 JSON schema 輸出，不要加任何 Markdown wrapping，直接輸出 JSON：
{OUTPUT_SCHEMA}

每個類別可以有 0 到多個 items。
- event_type 可為：product_announcement / partnership / acquisition / research / standard /
  market_data / policy / leadership / financial / other
- impact_assessment 請用中文，2-3 句說明對手機 SoC 產業的影響
- 若搜尋結果該類別無相關今日新聞，回傳空陣列 []
- 不要捏造，只從搜尋結果中提取事實"""

        try:
            resp = self.client.messages.create(
                model=INTEL_MODEL,
                max_tokens=SYNTHESIS_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text if resp.content else ""
            parsed = extract_json(text)
            if parsed:
                return parsed
            log("[Agent 1] Warning: could not parse synthesis JSON, returning empty structure")
        except Exception as e:
            log(f"[Agent 1] Synthesis error: {e}")

        return {k: [] for k, _ in SEARCH_QUERIES}

    @staticmethod
    def _total_items(report: IntelReport) -> int:
        return sum([
            len(report.competitor_dynamics),
            len(report.oem_moves),
            len(report.ecosystem_updates),
            len(report.operator_dynamics),
            len(report.app_trends),
            len(report.cpe_updates),
            len(report.tech_6g),
            len(report.chip_6g_moves),
            len(report.industry_structure),
        ])
