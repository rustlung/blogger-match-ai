from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class MatchDecision(str, Enum):
    RECOMMENDED = "recommended"
    REVIEW = "review"
    REJECTED = "rejected"


class RegionStatus(str, Enum):
    TARGET = "target"
    NON_TARGET = "non_target"
    UNKNOWN = "unknown"


class MatchCriterionScore(BaseModel):
    score: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    reason: str


class MatchCriteriaScores(BaseModel):
    thematic_fit: MatchCriterionScore
    audience_fit: MatchCriterionScore
    geography_fit: MatchCriterionScore
    language_fit: MatchCriterionScore
    account_size_fit: MatchCriterionScore
    engagement_fit: MatchCriterionScore
    content_style_fit: MatchCriterionScore
    commercial_fit: MatchCriterionScore


class BloggerMatchResult(BaseModel):
    profile_url: str
    username: str
    final_score: int = Field(ge=0, le=100)
    decision: MatchDecision
    region_status: RegionStatus
    region_confidence: int = Field(ge=0, le=100)
    detected_region: str | None = None
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    match_summary: str
    criteria_scores: MatchCriteriaScores

    @model_validator(mode="after")
    def validate_business_invariants(self) -> "BloggerMatchResult":
        if self.region_status == RegionStatus.NON_TARGET:
            if self.decision != MatchDecision.REJECTED:
                raise ValueError("non_target region requires rejected decision")
            if self.final_score != 0:
                raise ValueError("non_target region requires final_score = 0")
            if not self.rejection_reasons:
                raise ValueError("non_target region requires rejection_reasons")

        if self._detected_region_is_ukraine():
            if self.decision != MatchDecision.REJECTED:
                raise ValueError("Ukraine region requires rejected decision")
            if self.final_score != 0:
                raise ValueError("Ukraine region requires final_score = 0")
            if not self.rejection_reasons:
                raise ValueError("Ukraine region requires rejection_reasons")

        if self.decision == MatchDecision.RECOMMENDED and self.region_status != RegionStatus.TARGET:
            raise ValueError("recommended decision requires target region")

        if self.decision == MatchDecision.REJECTED and self.final_score > 40 and not self.rejection_reasons:
            raise ValueError("rejected decision with high score requires rejection_reasons")

        return self

    def _detected_region_is_ukraine(self) -> bool:
        if self.detected_region is None:
            return False
        normalized = self.detected_region.casefold()
        return "укра" in normalized or "ukrain" in normalized
