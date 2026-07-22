from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.batch_match_result import BatchMatchError
from src.models.batch_personalized_offer_result import BatchPersonalizedOfferResult
from src.models.blogger_match_result import MatchDecision
from src.models.personalized_offer import OfferStatus, PersonalizedOffer


def test_recommended_personalized_offer_requires_ready_status() -> None:
    offer = _offer(match_decision=MatchDecision.RECOMMENDED, offer_status=OfferStatus.READY)

    assert offer.match_decision == MatchDecision.RECOMMENDED
    assert offer.offer_status == OfferStatus.READY


def test_review_personalized_offer_requires_needs_review_and_notes() -> None:
    offer = _offer(
        match_decision=MatchDecision.REVIEW,
        offer_status=OfferStatus.NEEDS_REVIEW,
        manual_review_notes=["Проверить регион и формат интеграции."],
    )

    assert offer.offer_status == OfferStatus.NEEDS_REVIEW
    assert offer.manual_review_notes


def test_rejected_personalized_offer_is_invalid() -> None:
    with pytest.raises(ValidationError, match="rejected candidates"):
        _offer(
            match_decision=MatchDecision.REJECTED,
            offer_status=OfferStatus.NEEDS_REVIEW,
            manual_review_notes=["Не отправлять."],
        )


def test_personalized_offer_rejects_empty_message_and_points() -> None:
    with pytest.raises(ValidationError):
        _offer(message="")

    with pytest.raises(ValidationError):
        _offer(personalization_points=[])


def test_batch_personalized_offer_result_validates_counters() -> None:
    offer = _offer()
    error = BatchMatchError(
        profile_url="https://www.instagram.com/broken/",
        username="broken",
        error_type="LLMServiceError",
        error_message="Request failed.",
    )

    result = BatchPersonalizedOfferResult(
        offers=[offer],
        errors=[error],
        total_matches=3,
        eligible_candidates=2,
        skipped_rejected=1,
        successful_offers=1,
        failed_offers=1,
    )

    assert result.successful_offers == 1
    assert result.failed_offers == 1


def test_batch_personalized_offer_result_rejects_counter_mismatch() -> None:
    with pytest.raises(ValidationError, match="eligible_candidates"):
        BatchPersonalizedOfferResult(
            offers=[_offer()],
            errors=[],
            total_matches=1,
            eligible_candidates=0,
            skipped_rejected=0,
            successful_offers=1,
            failed_offers=0,
        )


def _offer(
    *,
    match_decision: MatchDecision = MatchDecision.RECOMMENDED,
    offer_status: OfferStatus = OfferStatus.READY,
    personalization_points: list[str] | None = None,
    manual_review_notes: list[str] | None = None,
    message: str = "Здравствуйте! Обратили внимание на ваш контент о семейном лайфстайле.",
) -> PersonalizedOffer:
    return PersonalizedOffer(
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        match_decision=match_decision,
        match_score=82,
        offer_status=offer_status,
        personalization_points=(
            ["Семейная тематика в описании профиля."]
            if personalization_points is None
            else personalization_points
        ),
        collaboration_angle="Контент близок к задачам кампании.",
        proposed_format="Короткий обзор или серия stories.",
        subject="Возможное сотрудничество",
        message=message,
        manual_review_notes=manual_review_notes or [],
    )
