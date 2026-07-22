from __future__ import annotations

from unittest.mock import Mock

import pytest

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
from src.services.llm_service import LLMServiceError
from src.services.personalized_offer_service import PersonalizedOfferService, PersonalizedOfferServiceError


def test_generate_offer_returns_typed_personalized_offer() -> None:
    offer = _offer()
    prompt_builder = _prompt_builder()
    llm_service = Mock()
    llm_service.generate_personalized_offer.return_value = offer

    result = PersonalizedOfferService(prompt_builder, llm_service).generate_offer(
        ideal_profile=_ideal_profile(),
        candidate_profile=_blogger(),
        match_result=_match_result(),
    )

    assert isinstance(result, PersonalizedOffer)
    assert result is offer
    prompt_builder.build_user_prompt.assert_called_once()
    llm_service.generate_personalized_offer.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )


def test_generate_offer_keeps_recommended_ready_and_review_needs_review() -> None:
    recommended = _offer(offer_status=OfferStatus.READY, match_decision=MatchDecision.RECOMMENDED)
    review_match = _match_result(decision=MatchDecision.REVIEW, final_score=55)
    review = _offer(
        offer_status=OfferStatus.NEEDS_REVIEW,
        match_decision=MatchDecision.REVIEW,
        match_score=55,
        manual_review_notes=["Проверить регион."],
    )

    assert _service_returning(recommended).generate_offer(_ideal_profile(), _blogger(), _match_result()).offer_status == OfferStatus.READY
    assert _service_returning(review).generate_offer(_ideal_profile(), _blogger(), review_match).offer_status == OfferStatus.NEEDS_REVIEW


def test_generate_offer_rejects_rejected_candidate_before_ai_call() -> None:
    prompt_builder = _prompt_builder()
    llm_service = Mock()

    with pytest.raises(PersonalizedOfferServiceError, match="rejected"):
        PersonalizedOfferService(prompt_builder, llm_service).generate_offer(
            ideal_profile=_ideal_profile(),
            candidate_profile=_blogger(),
            match_result=_match_result(decision=MatchDecision.REJECTED, final_score=0),
        )

    prompt_builder.build_system_prompt.assert_not_called()
    llm_service.generate_personalized_offer.assert_not_called()


def test_generate_offer_validates_match_score_decision_profile_url_and_username() -> None:
    with pytest.raises(PersonalizedOfferServiceError, match="match_score"):
        _service_returning(_offer(match_score=81)).generate_offer(_ideal_profile(), _blogger(), _match_result())

    with pytest.raises(PersonalizedOfferServiceError, match="match_decision"):
        _service_returning(
            _offer(
                match_decision=MatchDecision.REVIEW,
                offer_status=OfferStatus.NEEDS_REVIEW,
                manual_review_notes=["Проверить."],
            )
        ).generate_offer(_ideal_profile(), _blogger(), _match_result())

    with pytest.raises(PersonalizedOfferServiceError, match="profile_url"):
        _service_returning(_offer(profile_url="https://www.instagram.com/other/")).generate_offer(
            _ideal_profile(),
            _blogger(),
            _match_result(),
        )

    with pytest.raises(PersonalizedOfferServiceError, match="username"):
        _service_returning(_offer(username="other")).generate_offer(_ideal_profile(), _blogger(), _match_result())


def test_generate_offer_rejects_profile_and_match_identity_mismatch_before_ai_call() -> None:
    prompt_builder = _prompt_builder()
    llm_service = Mock()

    with pytest.raises(PersonalizedOfferServiceError, match="profile_url"):
        PersonalizedOfferService(prompt_builder, llm_service).generate_offer(
            ideal_profile=_ideal_profile(),
            candidate_profile=_blogger(profile_url="https://www.instagram.com/other/"),
            match_result=_match_result(),
        )

    with pytest.raises(PersonalizedOfferServiceError, match="username"):
        PersonalizedOfferService(prompt_builder, llm_service).generate_offer(
            ideal_profile=_ideal_profile(),
            candidate_profile=_blogger(username="other"),
            match_result=_match_result(),
        )

    llm_service.generate_personalized_offer.assert_not_called()


def test_generate_offer_propagates_ai_technical_error_without_ready_offer() -> None:
    prompt_builder = _prompt_builder()
    llm_service = Mock()
    llm_service.generate_personalized_offer.side_effect = LLMServiceError("LLM failed.")

    with pytest.raises(LLMServiceError, match="LLM failed"):
        PersonalizedOfferService(prompt_builder, llm_service).generate_offer(
            ideal_profile=_ideal_profile(),
            candidate_profile=_blogger(),
            match_result=_match_result(),
        )


def _service_returning(offer: PersonalizedOffer) -> PersonalizedOfferService:
    llm_service = Mock()
    llm_service.generate_personalized_offer.return_value = offer
    return PersonalizedOfferService(_prompt_builder(), llm_service)


def _prompt_builder() -> Mock:
    prompt_builder = Mock()
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    return prompt_builder


def _ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(niche="семейный лайфстайл", required_topics=["семья"])


def _blogger(
    *,
    profile_url: str = "https://www.instagram.com/creator/",
    username: str = "creator",
) -> BloggerProfile:
    return BloggerProfile(
        input_url=profile_url,
        profile_url=profile_url,
        username=username,
        biography="Short bio",
        followers_count=5000,
        raw_data={"username": username},
    )


def _offer(
    *,
    profile_url: str = "https://www.instagram.com/creator/",
    username: str = "creator",
    match_decision: MatchDecision = MatchDecision.RECOMMENDED,
    match_score: int = 82,
    offer_status: OfferStatus = OfferStatus.READY,
    manual_review_notes: list[str] | None = None,
) -> PersonalizedOffer:
    return PersonalizedOffer(
        profile_url=profile_url,
        username=username,
        match_decision=match_decision,
        match_score=match_score,
        offer_status=offer_status,
        personalization_points=["Семейная тематика в описании профиля."],
        collaboration_angle="Контент близок к задачам кампании.",
        proposed_format="Короткий обзор или серия stories.",
        subject="Возможное сотрудничество",
        message="Здравствуйте! Хотели бы обсудить аккуратное сотрудничество.",
        manual_review_notes=manual_review_notes or [],
    )


def _match_result(
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
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        final_score=final_score,
        decision=decision,
        region_status=region_status,
        region_confidence=80,
        detected_region=detected_region,
        strengths=["Тематика совпадает."],
        risks=["Недостаточно данных о вовлеченности."] if decision == MatchDecision.REVIEW else [],
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
