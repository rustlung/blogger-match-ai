from __future__ import annotations

import pytest

from src.models.batch_personalized_offer_result import BatchPersonalizedOfferResult
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.personalized_offer import OfferStatus, PersonalizedOffer
from src.services.batch_personalized_offer_service import (
    BatchPersonalizedOfferService,
    BatchPersonalizedOfferServiceError,
)
from src.services.personalized_offer_service import PersonalizedOfferServiceError


def test_batch_offer_service_processes_recommended_and_review_and_skips_rejected() -> None:
    offer_service = _offer_service(
        [
            _offer("recommended"),
            _offer("review", status=OfferStatus.NEEDS_REVIEW, decision=MatchDecision.REVIEW, score=55),
        ]
    )

    result = BatchPersonalizedOfferService(offer_service).generate_offers(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("recommended"), _blogger("review"), _blogger("rejected")],
        match_results=[
            _match_result("recommended"),
            _match_result("review", decision=MatchDecision.REVIEW, final_score=55),
            _match_result("rejected", decision=MatchDecision.REJECTED, final_score=0),
        ],
    )

    assert [call[2].username for call in offer_service.calls] == ["recommended", "review"]
    assert result.skipped_rejected == 1
    assert result.eligible_candidates == 2
    assert result.successful_offers == 2


def test_batch_offer_service_matches_profiles_by_url_not_position() -> None:
    offer_service = _offer_service([_offer("first"), _offer("second")])

    BatchPersonalizedOfferService(offer_service).generate_offers(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("second"), _blogger("first")],
        match_results=[_match_result("first"), _match_result("second")],
    )

    assert [call[1].username for call in offer_service.calls] == ["first", "second"]


def test_batch_offer_service_records_missing_profile_as_technical_error() -> None:
    offer_service = _offer_service([_offer("found")])

    result = BatchPersonalizedOfferService(offer_service).generate_offers(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("found")],
        match_results=[_match_result("missing"), _match_result("found")],
    )

    assert result.errors[0].error_type == "ProfileNotFound"
    assert result.failed_offers == 1
    assert result.successful_offers == 1


def test_batch_offer_service_continues_after_one_generation_error() -> None:
    offer_service = _offer_service([PersonalizedOfferServiceError("LLM failed."), _offer("second")])

    result = BatchPersonalizedOfferService(offer_service).generate_offers(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("first"), _blogger("second")],
        match_results=[_match_result("first"), _match_result("second")],
    )

    assert result.errors[0].username == "first"
    assert [offer.username for offer in result.offers] == ["second"]


def test_batch_offer_service_all_rejected_is_successful_empty_result_without_ai_calls() -> None:
    offer_service = _offer_service([])

    result = BatchPersonalizedOfferService(offer_service).generate_offers(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("rejected")],
        match_results=[_match_result("rejected", decision=MatchDecision.REJECTED, final_score=0)],
    )

    assert result.offers == []
    assert result.errors == []
    assert result.skipped_rejected == 1
    assert result.eligible_candidates == 0
    assert offer_service.calls == []


def test_batch_offer_service_raises_when_all_eligible_generations_fail() -> None:
    offer_service = _offer_service([RuntimeError("first failed"), RuntimeError("second failed")])

    with pytest.raises(BatchPersonalizedOfferServiceError, match="ни одного") as exc_info:
        BatchPersonalizedOfferService(offer_service).generate_offers(
            ideal_profile=_ideal_profile(),
            candidate_profiles=[_blogger("first"), _blogger("second")],
            match_results=[_match_result("first"), _match_result("second")],
        )

    result = exc_info.value.result
    assert isinstance(result, BatchPersonalizedOfferResult)
    assert result.successful_offers == 0
    assert result.failed_offers == 2


def test_batch_offer_service_sorts_ready_before_needs_review_then_score_and_username() -> None:
    offer_service = _offer_service(
        [
            _offer("zeta", score=60, status=OfferStatus.NEEDS_REVIEW, decision=MatchDecision.REVIEW),
            _offer("beta", score=80),
            _offer("alpha", score=80),
            _offer("gamma", score=70, status=OfferStatus.NEEDS_REVIEW, decision=MatchDecision.REVIEW),
        ]
    )

    result = BatchPersonalizedOfferService(offer_service).generate_offers(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("zeta"), _blogger("beta"), _blogger("alpha"), _blogger("gamma")],
        match_results=[
            _match_result("zeta", decision=MatchDecision.REVIEW, final_score=60),
            _match_result("beta", final_score=80),
            _match_result("alpha", final_score=80),
            _match_result("gamma", decision=MatchDecision.REVIEW, final_score=70),
        ],
    )

    assert [offer.username for offer in result.offers] == ["alpha", "beta", "gamma", "zeta"]


def _ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(niche="семейный лайфстайл")


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        biography="Short bio",
        raw_data={"username": username},
    )


def _offer(
    username: str,
    *,
    score: int = 82,
    status: OfferStatus = OfferStatus.READY,
    decision: MatchDecision = MatchDecision.RECOMMENDED,
) -> PersonalizedOffer:
    return PersonalizedOffer(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        match_decision=decision,
        match_score=score,
        offer_status=status,
        personalization_points=["Наблюдаемая тематика профиля."],
        collaboration_angle="Контент близок к задачам кампании.",
        proposed_format="Короткое видео или stories.",
        subject="Возможное сотрудничество",
        message="Здравствуйте! Хотели бы обсудить аккуратное сотрудничество.",
        manual_review_notes=["Проверить риски."] if status == OfferStatus.NEEDS_REVIEW else [],
    )


def _match_result(
    username: str,
    *,
    decision: MatchDecision = MatchDecision.RECOMMENDED,
    final_score: int = 82,
) -> BloggerMatchResult:
    region_status = RegionStatus.TARGET
    detected_region: str | None = "Россия"
    rejection_reasons: list[str] = []
    if decision == MatchDecision.REVIEW:
        region_status = RegionStatus.UNKNOWN
        detected_region = None
    if decision == MatchDecision.REJECTED:
        region_status = RegionStatus.NON_TARGET
        detected_region = "Украина"
        rejection_reasons = ["Не целевой регион."]

    return BloggerMatchResult(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        final_score=final_score,
        decision=decision,
        region_status=region_status,
        region_confidence=80,
        detected_region=detected_region,
        strengths=["Тематика совпадает."],
        risks=["Регион не подтвержден."] if decision == MatchDecision.REVIEW else [],
        rejection_reasons=rejection_reasons,
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


def _offer_service(results: list[PersonalizedOffer | Exception]):
    class FakeOfferService:
        def __init__(self) -> None:
            self.calls: list[tuple[IdealBloggerProfile, BloggerProfile, BloggerMatchResult]] = []
            self._results = list(results)

        def generate_offer(
            self,
            ideal_profile: IdealBloggerProfile,
            candidate_profile: BloggerProfile,
            match_result: BloggerMatchResult,
        ) -> PersonalizedOffer:
            self.calls.append((ideal_profile, candidate_profile, match_result))
            result = self._results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    return FakeOfferService()
