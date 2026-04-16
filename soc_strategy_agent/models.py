from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IntelItem(BaseModel):
    company: str
    event_type: str
    title: str
    summary: str
    impact_assessment: str
    source_url: str = ""
    source_name: str = ""
    published_date: str = ""


class IntelReport(BaseModel):
    topic: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    competitor_dynamics: list[IntelItem] = Field(
        default_factory=list,
        description="Apple/Qualcomm/MediaTek chip and AI announcements",
    )
    oem_moves: list[IntelItem] = Field(
        default_factory=list,
        description="Chinese OEM (Xiaomi/OPPO/vivo/Huawei) and Samsung moves",
    )
    ecosystem_updates: list[IntelItem] = Field(
        default_factory=list,
        description="Google/Android/Gemini AI agent ecosystem updates",
    )
    operator_dynamics: list[IntelItem] = Field(
        default_factory=list,
        description="Mobile operator 5G/6G/AI-native network updates",
    )
    app_trends: list[IntelItem] = Field(
        default_factory=list,
        description="Killer app and super app AI agent integration trends",
    )
    cpe_updates: list[IntelItem] = Field(
        default_factory=list,
        description="CPE / home router / Wi-Fi 7 / AI gateway updates",
    )
    tech_6g: list[IntelItem] = Field(
        default_factory=list,
        description="6G IMT-2030 / 3GPP standard research updates",
    )
    chip_6g_moves: list[IntelItem] = Field(
        default_factory=list,
        description="Apple/Qualcomm/MediaTek/Samsung 6G chip and research moves",
    )
    industry_structure: list[IntelItem] = Field(
        default_factory=list,
        description="M&A, investment, partnership, policy changes",
    )

    all_sources: list[str] = Field(default_factory=list)
    search_queries_used: list[str] = Field(default_factory=list)
