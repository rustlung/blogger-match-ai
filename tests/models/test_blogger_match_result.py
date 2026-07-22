from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)


def test_recommended_match_result_passes_validation() -> None:
    result = _match_result(
        final_score=88,
        decision=MatchDecision.RECOMMENDED,
        region_status=RegionStatus.TARGET,
        detected_region="Россия",
    )

    assert result.final_score == 88
    assert result.decision == MatchDecision.RECOMMENDED
    assert result.region_status == RegionStatus.TARGET


def test_review_match_result_with_unknown_region_passes_validation() -> None:
    result = _match_result(
        final_score=55,
        decision=MatchDecision.REVIEW,
        region_status=RegionStatus.UNKNOWN,
        detected_region=None,
        risks=["Регион не подтвержден надежными признаками."],
    )

    assert result.region_status == RegionStatus.UNKNOWN
    assert result.detected_region is None
    assert result.risks == ["Регион не подтвержден надежными признаками."]


def test_non_target_region_requires_rejected_decision_zero_score_and_reason() -> None:
    with pytest.raises(ValidationError, match="non_target region requires rejected decision"):
        _match_result(
            final_score=80,
            decision=MatchDecision.RECOMMENDED,
            region_status=RegionStatus.NON_TARGET,
            detected_region="Украина",
            rejection_reasons=["Украинский рынок не является целевым."],
        )


def test_ukraine_region_requires_rejected_zero_score_and_rejection_reason() -> None:
    result = _match_result(
        final_score=0,
        decision=MatchDecision.REJECTED,
        region_status=RegionStatus.NON_TARGET,
        detected_region="Украина",
        rejection_reasons=["Есть надежные признаки ориентации на украинский рынок."],
    )

    assert result.decision == MatchDecision.REJECTED
    assert result.final_score == 0
    assert result.rejection_reasons


def test_ukraine_region_with_positive_score_is_rejected_by_validation() -> None:
    with pytest.raises(ValidationError, match="final_score = 0"):
        _match_result(
            final_score=20,
            decision=MatchDecision.REJECTED,
            region_status=RegionStatus.NON_TARGET,
            detected_region="Ukraine",
            rejection_reasons=["Не целевой рынок."],
        )


def test_russian_language_without_region_evidence_does_not_require_target_region() -> None:
    result = _match_result(
        final_score=50,
        decision=MatchDecision.REVIEW,
        region_status=RegionStatus.UNKNOWN,
        detected_region=None,
        risks=["Русский язык сам по себе не подтверждает российский рынок."],
    )

    assert result.region_status == RegionStatus.UNKNOWN


def test_invalid_final_score_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _match_result(final_score=101)


def test_contradictory_non_target_recommended_result_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _match_result(
            final_score=90,
            decision=MatchDecision.RECOMMENDED,
            region_status=RegionStatus.NON_TARGET,
            rejection_reasons=["Не целевой регион."],
        )


def test_low_confidence_and_risks_represent_insufficient_data() -> None:
    result = _match_result(
        final_score=45,
        decision=MatchDecision.REVIEW,
        region_status=RegionStatus.UNKNOWN,
        region_confidence=10,
        risks=["Недостаточно данных о регионе и аудитории."],
        criteria_scores=_criteria_scores(geography_confidence=10, engagement_confidence=5),
    )

    assert result.region_confidence == 10
    assert result.criteria_scores.geography_fit.confidence == 10
    assert result.criteria_scores.engagement_fit.confidence == 5
    assert result.risks


def _match_result(
    *,
    final_score: int = 80,
    decision: MatchDecision = MatchDecision.RECOMMENDED,
    region_status: RegionStatus = RegionStatus.TARGET,
    region_confidence: int = 80,
    detected_region: str | None = "Россия",
    risks: list[str] | None = None,
    rejection_reasons: list[str] | None = None,
    criteria_scores: MatchCriteriaScores | None = None,
) -> BloggerMatchResult:
    return BloggerMatchResult(
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        final_score=final_score,
        decision=decision,
        region_status=region_status,
        region_confidence=region_confidence,
        detected_region=detected_region,
        strengths=["Тематика соответствует идеальному профилю."],
        risks=risks or [],
        rejection_reasons=rejection_reasons or [],
        match_summary="Кандидат соответствует основным требованиям.",
        criteria_scores=criteria_scores or _criteria_scores(),
    )


def _criteria_scores(geography_confidence: int = 80, engagement_confidence: int = 60) -> MatchCriteriaScores:
    return MatchCriteriaScores(
        thematic_fit=_criterion(85, 80, "Тематика совпадает."),
        audience_fit=_criterion(70, 50, "Демография аудитории не подтверждена."),
        geography_fit=_criterion(80, geography_confidence, "Есть признаки целевого рынка."),
        language_fit=_criterion(75, 60, "Профиль русскоязычный, но язык не доказывает регион."),
        account_size_fit=_criterion(80, 90, "Размер аккаунта подходит."),
        engagement_fit=_criterion(40, engagement_confidence, "Нет надежных данных о вовлеченности."),
        content_style_fit=_criterion(80, 70, "Стиль близок к требованиям."),
        commercial_fit=_criterion(75, 65, "Есть признаки коммерческой пригодности."),
    )


def _criterion(score: int, confidence: int, reason: str) -> MatchCriterionScore:
    return MatchCriterionScore(score=score, confidence=confidence, reason=reason)
