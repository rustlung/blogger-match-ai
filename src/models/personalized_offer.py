from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from src.models.blogger_match_result import MatchDecision


class OfferStatus(str, Enum):
    READY = "ready"
    NEEDS_REVIEW = "needs_review"


class PersonalizedOffer(BaseModel):
    profile_url: str
    username: str
    match_decision: MatchDecision
    match_score: int = Field(ge=0, le=100)
    offer_status: OfferStatus
    personalization_points: list[str] = Field(min_length=1, max_length=5)
    collaboration_angle: str = Field(min_length=1, max_length=500)
    proposed_format: str = Field(min_length=1, max_length=250)
    subject: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1200)
    manual_review_notes: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_offer_invariants(self) -> "PersonalizedOffer":
        if self.match_decision == MatchDecision.REJECTED:
            raise ValueError("rejected candidates cannot have personalized offers")

        if self.match_decision == MatchDecision.RECOMMENDED and self.offer_status != OfferStatus.READY:
            raise ValueError("recommended offers must have ready status")

        if self.match_decision == MatchDecision.REVIEW:
            if self.offer_status != OfferStatus.NEEDS_REVIEW:
                raise ValueError("review offers must have needs_review status")
            if not self.manual_review_notes:
                raise ValueError("review offers require manual_review_notes")

        return self
