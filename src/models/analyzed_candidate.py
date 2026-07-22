from __future__ import annotations

from pydantic import BaseModel

from src.models.blogger import BloggerProfile
from src.models.candidate_analysis import CandidateAnalysis


class AnalyzedCandidate(BaseModel):
    blogger: BloggerProfile
    analysis: CandidateAnalysis
