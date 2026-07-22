from __future__ import annotations

from pydantic import BaseModel, Field


class CandidateAnalysis(BaseModel):
    overall_score: float
    niche_match_score: float
    audience_match_score: float
    content_quality_score: float
    brand_safety_score: float
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendation: str
    explanation: str
    confidence: float
