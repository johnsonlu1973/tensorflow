"""Configuration for SOC Planning Agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "soc_planning.db"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-6"

# Daily collection focuses
DAILY_TOPICS = [
    "3GPP latest standard releases and work items (Release 18, Release 19, Release 20)",
    "AI agent and LLM integration in telecom and network infrastructure",
    "5G/6G chipset and SoC market competitive landscape",
    "Qualcomm, MediaTek, Samsung Exynos, Apple Silicon latest announcements",
    "Open RAN and vRAN SoC technology developments",
    "Edge AI and on-device inference chip trends",
]

# Weekly deep-dive analysis themes
WEEKLY_THEMES = [
    "Cross-analysis: 3GPP standards roadmap vs SoC product gap analysis",
    "Competitive positioning: feature comparison and market share shifts",
    "AI/ML acceleration requirements in next-gen baseband SoCs",
    "Technology trend synthesis and 12-month product roadmap recommendations",
]

# Search queries for data collection
SEARCH_QUERIES = {
    "3gpp": [
        "3GPP Release 18 19 20 latest approved specifications 2024 2025",
        "3GPP new work items radio access network chipset requirements",
        "3GPP 5G-Advanced features timeline standardization",
    ],
    "market_trends": [
        "AI agent integration telecom infrastructure SoC 2025",
        "on-device LLM inference mobile chipset requirements",
        "6G research chipset technology roadmap",
    ],
    "competitors": [
        "Qualcomm Snapdragon X Elite X85 modem baseband announcement",
        "MediaTek Dimensity modem SoC latest release specs",
        "Samsung Exynos 2500 baseband modem specification",
        "Apple M4 A18 modem integration latest news",
    ],
}
