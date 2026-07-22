from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.ideal_blogger_profile import IdealBloggerProfile


class IdealProfileAnalysis(BaseModel):
    ideal_profile: IdealBloggerProfile
    source_profiles_count: int = Field(ge=1)
    common_traits: list[str] = Field(default_factory=list)
    important_selection_criteria: list[str] = Field(default_factory=list)
    observed_variations: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    explanation: str
    confidence: float = Field(ge=0, le=100)
