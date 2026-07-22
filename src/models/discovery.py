from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoveryCandidate(BaseModel):
    username: str
    profile_url: str
    source_query: str
    title: str | None = None
    description: str | None = None


class DiscoveryResult(BaseModel):
    queries: list[str] = Field(default_factory=list)
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    total_candidates: int
