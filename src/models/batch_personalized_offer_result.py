from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from src.models.batch_match_result import BatchMatchError
from src.models.personalized_offer import PersonalizedOffer


class BatchPersonalizedOfferResult(BaseModel):
    offers: list[PersonalizedOffer] = Field(default_factory=list)
    errors: list[BatchMatchError] = Field(default_factory=list)
    total_matches: int = Field(ge=0)
    eligible_candidates: int = Field(ge=0)
    skipped_rejected: int = Field(ge=0)
    successful_offers: int = Field(ge=0)
    failed_offers: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counters(self) -> "BatchPersonalizedOfferResult":
        if self.successful_offers != len(self.offers):
            raise ValueError("successful_offers must equal len(offers)")
        if self.failed_offers != len(self.errors):
            raise ValueError("failed_offers must equal len(errors)")
        if self.eligible_candidates != self.successful_offers + self.failed_offers:
            raise ValueError("eligible_candidates must equal successful_offers + failed_offers")
        if self.total_matches != self.eligible_candidates + self.skipped_rejected:
            raise ValueError("total_matches must equal eligible_candidates + skipped_rejected")
        return self
