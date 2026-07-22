from __future__ import annotations

from pydantic import BaseModel, Field


class IdealBloggerProfile(BaseModel):
    niche: str
    target_gender: str | None = None
    target_age_range: str | None = None
    min_followers: int | None = None
    max_followers: int | None = None
    required_topics: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    preferred_regions: list[str] = Field(default_factory=list)
    preferred_languages: list[str] = Field(default_factory=list)
    required_brand_style: str | None = None
