from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.blogger import BloggerProfile
from src.models.failed_profile import FailedProfile


class ApifyEnrichmentResult(BaseModel):
    profiles: list[BloggerProfile] = Field(default_factory=list)
    failed_profiles: list[FailedProfile] = Field(default_factory=list)
