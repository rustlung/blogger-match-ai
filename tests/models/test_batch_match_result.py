from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.batch_match_result import BatchMatchError, BatchMatchResult
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)


def test_batch_match_result_accepts_consistent_counters() -> None:
    result = BatchMatchResult(
        matches=[_match_result("creator")],
        errors=[_match_error("broken")],
        total_candidates=2,
        successful_matches=1,
        failed_matches=1,
    )

    assert result.successful_matches == 1
    assert result.failed_matches == 1


def test_batch_match_result_rejects_success_counter_mismatch() -> None:
    with pytest.raises(ValidationError, match="successful_matches"):
        BatchMatchResult(
            matches=[_match_result("creator")],
            errors=[],
            total_candidates=1,
            successful_matches=0,
            failed_matches=0,
        )


def test_batch_match_result_rejects_failed_counter_mismatch() -> None:
    with pytest.raises(ValidationError, match="failed_matches"):
        BatchMatchResult(
            matches=[],
            errors=[_match_error("broken")],
            total_candidates=1,
            successful_matches=0,
            failed_matches=0,
        )


def test_batch_match_result_rejects_total_counter_mismatch() -> None:
    with pytest.raises(ValidationError, match="total_candidates"):
        BatchMatchResult(
            matches=[_match_result("creator")],
            errors=[],
            total_candidates=2,
            successful_matches=1,
            failed_matches=0,
        )


def _match_error(username: str) -> BatchMatchError:
    return BatchMatchError(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        error_type="LLMServiceError",
        error_message="LLM request timed out.",
    )


def _match_result(username: str) -> BloggerMatchResult:
    return BloggerMatchResult(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        final_score=80,
        decision=MatchDecision.RECOMMENDED,
        region_status=RegionStatus.TARGET,
        region_confidence=80,
        detected_region="Россия",
        strengths=["Тематика совпадает."],
        risks=[],
        rejection_reasons=[],
        match_summary="Кандидат подходит.",
        criteria_scores=_criteria_scores(),
    )


def _criteria_scores() -> MatchCriteriaScores:
    return MatchCriteriaScores(
        thematic_fit=_criterion(),
        audience_fit=_criterion(),
        geography_fit=_criterion(),
        language_fit=_criterion(),
        account_size_fit=_criterion(),
        engagement_fit=_criterion(),
        content_style_fit=_criterion(),
        commercial_fit=_criterion(),
    )


def _criterion() -> MatchCriterionScore:
    return MatchCriterionScore(score=80, confidence=70, reason="Тестовая причина.")
