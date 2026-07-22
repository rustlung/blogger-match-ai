from __future__ import annotations

import re

from src.models.batch_match_result import BatchMatchError
from src.models.batch_personalized_offer_result import BatchPersonalizedOfferResult
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import BloggerMatchResult, MatchDecision
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.personalized_offer import OfferStatus, PersonalizedOffer
from src.services.personalized_offer_service import PersonalizedOfferService
from src.utils.logger import logger


class BatchPersonalizedOfferServiceError(RuntimeError):
    def __init__(self, message: str, result: BatchPersonalizedOfferResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class BatchPersonalizedOfferService:
    def __init__(self, offer_service: PersonalizedOfferService) -> None:
        self._offer_service = offer_service

    def generate_offers(
        self,
        ideal_profile: IdealBloggerProfile,
        candidate_profiles: list[BloggerProfile],
        match_results: list[BloggerMatchResult],
    ) -> BatchPersonalizedOfferResult:
        profile_index = _ProfileIndex(candidate_profiles)
        offers: list[PersonalizedOffer] = []
        errors: list[BatchMatchError] = []
        skipped_rejected = 0

        for match_result in match_results:
            if match_result.decision == MatchDecision.REJECTED:
                skipped_rejected += 1
                continue

            candidate_profile, lookup_error = profile_index.find(match_result)
            if lookup_error is not None:
                errors.append(lookup_error)
                logger.warning(
                    "Personalized offer profile lookup failed: username=%s error_type=%s message=%s",
                    lookup_error.username or "-",
                    lookup_error.error_type,
                    lookup_error.error_message,
                )
                continue

            try:
                offer = self._offer_service.generate_offer(
                    ideal_profile=ideal_profile,
                    candidate_profile=candidate_profile,
                    match_result=match_result,
                )
            except Exception as exc:
                error = BatchMatchError(
                    profile_url=match_result.profile_url,
                    username=match_result.username,
                    error_type=type(exc).__name__,
                    error_message=_safe_error_message(exc),
                )
                errors.append(error)
                logger.warning(
                    "Personalized offer generation failed in batch: username=%s error_type=%s message=%s",
                    error.username or "-",
                    error.error_type,
                    error.error_message,
                )
                continue

            offers.append(offer)

        eligible_candidates = len(match_results) - skipped_rejected
        result = BatchPersonalizedOfferResult(
            offers=_sort_offers(offers),
            errors=errors,
            total_matches=len(match_results),
            eligible_candidates=eligible_candidates,
            skipped_rejected=skipped_rejected,
            successful_offers=len(offers),
            failed_offers=len(errors),
        )

        if result.eligible_candidates > 0 and not result.offers:
            raise BatchPersonalizedOfferServiceError(
                "Не удалось создать ни одного персонализированного предложения.",
                result=result,
            )

        return result


class _ProfileIndex:
    def __init__(self, profiles: list[BloggerProfile]) -> None:
        self._by_url: dict[str, list[BloggerProfile]] = {}
        self._by_username: dict[str, list[BloggerProfile]] = {}
        for profile in profiles:
            self._by_url.setdefault(_normalize_key(profile.profile_url), []).append(profile)
            self._by_username.setdefault(profile.username.casefold(), []).append(profile)

    def find(self, match_result: BloggerMatchResult) -> tuple[BloggerProfile, None] | tuple[None, BatchMatchError]:
        url_key = _normalize_key(match_result.profile_url)
        url_profiles = self._by_url.get(url_key, [])
        if len(url_profiles) == 1:
            return url_profiles[0], None
        if len(url_profiles) > 1:
            return None, _lookup_error(match_result, "AmbiguousProfileMatch", "Найдено несколько профилей с тем же profile_url.")

        username_profiles = self._by_username.get(match_result.username.casefold(), [])
        if len(username_profiles) == 1:
            return username_profiles[0], None
        if len(username_profiles) > 1:
            return None, _lookup_error(match_result, "AmbiguousProfileMatch", "Найдено несколько профилей с тем же username.")

        return None, _lookup_error(match_result, "ProfileNotFound", "Не найден BloggerProfile для результата Matcher.")


def _lookup_error(match_result: BloggerMatchResult, error_type: str, error_message: str) -> BatchMatchError:
    return BatchMatchError(
        profile_url=match_result.profile_url,
        username=match_result.username,
        error_type=error_type,
        error_message=error_message,
    )


def _sort_offers(offers: list[PersonalizedOffer]) -> list[PersonalizedOffer]:
    status_order = {
        OfferStatus.READY: 0,
        OfferStatus.NEEDS_REVIEW: 1,
    }
    return sorted(
        offers,
        key=lambda offer: (
            status_order[offer.offer_status],
            -offer.match_score,
            offer.username.casefold(),
            offer.profile_url,
        ),
    )


def _normalize_key(value: str) -> str:
    return value.strip().rstrip("/").casefold()


def _safe_error_message(exc: Exception) -> str:
    message = " ".join(str(exc).split()) or "Unknown technical error."
    message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.IGNORECASE)
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-[redacted]", message)
    message = re.sub(r"(api[_-]?key=)[^\s&]+", r"\1[redacted]", message, flags=re.IGNORECASE)
    return message[:300]
