from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from src.models.blogger_match_result import BloggerMatchResult


class BatchMatchError(BaseModel):
    profile_url: str | None = None
    username: str | None = None
    error_type: str
    error_message: str


class BatchMatchResult(BaseModel):
    matches: list[BloggerMatchResult] = Field(default_factory=list)
    errors: list[BatchMatchError] = Field(default_factory=list)
    total_candidates: int = Field(ge=0)
    successful_matches: int = Field(ge=0)
    failed_matches: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counters(self) -> "BatchMatchResult":
        if self.successful_matches != len(self.matches):
            raise ValueError("successful_matches must equal len(matches)")
        if self.failed_matches != len(self.errors):
            raise ValueError("failed_matches must equal len(errors)")
        if self.total_candidates != self.successful_matches + self.failed_matches:
            raise ValueError("total_candidates must equal successful_matches + failed_matches")
        return self
