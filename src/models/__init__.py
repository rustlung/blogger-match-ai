from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.batch_match_result import BatchMatchError, BatchMatchResult
from src.models.batch_personalized_offer_result import BatchPersonalizedOfferResult
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.models.candidate_analysis import CandidateAnalysis
from src.models.discovery import DiscoveryCandidate, DiscoveryResult
from src.models.failed_profile import FailedProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.models.personalized_offer import OfferStatus, PersonalizedOffer


__all__ = [
    "AnalyzedCandidate",
    "ApifyEnrichmentResult",
    "BatchMatchError",
    "BatchMatchResult",
    "BatchPersonalizedOfferResult",
    "BloggerProfile",
    "BloggerMatchResult",
    "CandidateAnalysis",
    "DiscoveryCandidate",
    "DiscoveryResult",
    "FailedProfile",
    "IdealBloggerProfile",
    "IdealProfileAnalysis",
    "MatchCriteriaScores",
    "MatchCriterionScore",
    "MatchDecision",
    "OfferStatus",
    "PersonalizedOffer",
    "RegionStatus",
]
