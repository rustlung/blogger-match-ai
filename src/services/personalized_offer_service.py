from __future__ import annotations

from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import BloggerMatchResult, MatchDecision
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.personalized_offer import OfferStatus, PersonalizedOffer
from src.services.llm_service import LLMService
from src.services.personalized_offer_prompt_builder import PersonalizedOfferPromptBuilder
from src.utils.logger import logger


class PersonalizedOfferServiceError(RuntimeError):
    pass


class PersonalizedOfferService:
    def __init__(
        self,
        prompt_builder: PersonalizedOfferPromptBuilder,
        llm_service: LLMService,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service

    def generate_offer(
        self,
        ideal_profile: IdealBloggerProfile,
        candidate_profile: BloggerProfile,
        match_result: BloggerMatchResult,
    ) -> PersonalizedOffer:
        _validate_candidate_identity(candidate_profile, match_result)

        if match_result.decision == MatchDecision.REJECTED:
            raise PersonalizedOfferServiceError("Для rejected-кандидата предложение не генерируется.")

        logger.info("Personalized offer generation started: username=%s", candidate_profile.username)

        try:
            system_prompt = self._prompt_builder.build_system_prompt()
            user_prompt = self._prompt_builder.build_user_prompt(
                ideal_profile=ideal_profile,
                candidate_profile=candidate_profile,
                match_result=match_result,
            )
            offer = self._llm_service.generate_personalized_offer(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.error(
                "Personalized offer generation failed: username=%s error_type=%s",
                candidate_profile.username,
                type(exc).__name__,
            )
            raise

        _validate_offer_matches_result(offer, candidate_profile, match_result)

        logger.info(
            "Personalized offer generation completed: username=%s status=%s",
            offer.username,
            offer.offer_status.value,
        )
        return offer


def _validate_candidate_identity(candidate_profile: BloggerProfile, match_result: BloggerMatchResult) -> None:
    if _normalize_url(candidate_profile.profile_url) != _normalize_url(match_result.profile_url):
        raise PersonalizedOfferServiceError("BloggerProfile и BloggerMatchResult относятся к разным profile_url.")

    if candidate_profile.username.casefold() != match_result.username.casefold():
        raise PersonalizedOfferServiceError("BloggerProfile и BloggerMatchResult относятся к разным username.")


def _validate_offer_matches_result(
    offer: PersonalizedOffer,
    candidate_profile: BloggerProfile,
    match_result: BloggerMatchResult,
) -> None:
    if _normalize_url(offer.profile_url) != _normalize_url(candidate_profile.profile_url):
        raise PersonalizedOfferServiceError("PersonalizedOffer содержит неверный profile_url.")

    if offer.username.casefold() != candidate_profile.username.casefold():
        raise PersonalizedOfferServiceError("PersonalizedOffer содержит неверный username.")

    if offer.match_decision != match_result.decision:
        raise PersonalizedOfferServiceError("PersonalizedOffer содержит неверный match_decision.")

    if offer.match_score != match_result.final_score:
        raise PersonalizedOfferServiceError("PersonalizedOffer содержит неверный match_score.")

    expected_status = OfferStatus.READY
    if match_result.decision == MatchDecision.REVIEW:
        expected_status = OfferStatus.NEEDS_REVIEW

    if offer.offer_status != expected_status:
        raise PersonalizedOfferServiceError("PersonalizedOffer содержит неверный offer_status.")


def _normalize_url(value: str) -> str:
    return value.strip().rstrip("/").casefold()
