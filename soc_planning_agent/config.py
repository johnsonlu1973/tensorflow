"""Configuration for SOC Planning Agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "soc_planning.db"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model tiers: Haiku for collection (10x cheaper), Opus for deep analysis
MODEL = "claude-opus-4-6"
COLLECTION_MODEL = "claude-haiku-4-5"

# Daily RSS collection focus areas (informational — see rss_collector.py for actual sources)
DAILY_TOPICS = [
    "Agentic AI — multi-agent systems, autonomous agents, on-device LLM",
    "Chips/SoC — mobile SoC, baseband, NPU, AI accelerators, semiconductor news",
    "Mobile — smartphone OEM announcements, flagship launches, 5G phones",
    "5G CPE — Fixed Wireless Access, O-RAN, network slicing, 5G-Advanced",
    "CSP/Cloud — AWS, Azure, GCP infrastructure and AI services",
]

# Weekly analysis themes (used by run_weekly_analysis)
WEEKLY_THEMES = [
    "Cross-analysis: 3GPP standards roadmap vs SoC product gap analysis",
    "Competitive positioning: feature comparison and market share shifts",
    "AI/ML acceleration requirements in next-gen baseband SoCs",
    "Technology trend synthesis and 12-month product roadmap recommendations",
]

# Fallback web_search queries used when direct RSS fetch is blocked by network.
# Targets the same vetted sources via site: operator searches.
# NOTE:Year is intentionally not hardcoded here — agent.py injects today's date at runtime.
FALLBACK_SEARCH_QUERIES = {
    "agentic_ai": [
        "site:techcrunch.com OR site:venturebeat.com agentic AI agent LLM autonomous latest news",
        "site:spectrum.ieee.org OR site:technologyreview.com AI agent on-device inference latest",
    ],
    "chips_soc": [
        "site:eetimes.com OR site:semianalysis.com SoC chipset modem AI accelerator latest news",
        "site:tomshardware.com OR site:semiengineering.com semiconductor chip announcement latest",
    ],
    "mobile": [
        "site:gsmarena.com OR site:theverge.com smartphone 5G Android iPhone flagship latest",
        "site:androidauthority.com OR site:fiercewireless.com mobile OEM chipset announcement latest",
    ],
    "5g_cpe": [
        "site:lightreading.com OR site:rcrwireless.com 5G CPE O-RAN telecom latest news",
        "site:fiercetelecom.com OR site:telecomtv.com 5G-Advanced fixed wireless access latest",
    ],
    "csp_cloud": [
        "site:thenewstack.io OR site:siliconangle.com cloud AI infrastructure hyperscaler latest news",
        "site:aws.amazon.com/blogs OR site:cloud.google.com/blog cloud services AI announcement latest",
    ],
}

# Web search queries for weekly 3GPP + vendor/operator updates.
# These supplement the RSS vendor feeds with targeted 3GPP spec searches.
THREEGPP_WEEKLY_QUERIES = {
    "3gpp_specs": [
        "3GPP Release 19 Release 20 new approved work items specifications 2026",
        "3GPP 5G-Advanced NR features timeline standardization 2026",
        "3GPP TSG RAN SA CT latest meeting decisions plenary 2026",
    ],
    "vendors_news": [
        "Nokia Ericsson 5G-Advanced RAN baseband chipset announcement 2026",
        "Huawei ZTE 5G base station SoC technology announcement 2026",
    ],
    "operators_news": [
        "T-Mobile Verizon AT&T China Mobile Vodafone 5G deployment strategy 2026",
        "global operator 5G-Advanced network commercial launch 2026",
    ],
}
