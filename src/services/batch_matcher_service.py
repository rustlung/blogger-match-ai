from __future__ import annotations

import re

from src.models.batch_match_result import BatchMatchError, BatchMatchResult
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import BloggerMatchResult, MatchDecision
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.matcher_service import MatcherService
from src.utils.logger import logger


class BatchMatcherServiceError(RuntimeError):
    def __init__(self, message: str, result: BatchMatchResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class BatchMatcherService:
    def __init__(self, matcher_service: MatcherService) -> None:
        self._matcher_service = matcher_service

    def match_candidates(
        self,
        ideal_profile: IdealBloggerProfile,
        candidate_profiles: list[BloggerProfile],
    ) -> BatchMatchResult:
        if not candidate_profiles:
            raise BatchMatcherServiceError("Нет кандидатов для оценки.")

        matches: list[BloggerMatchResult] = []
        errors: list[BatchMatchError] = []

        for candidate_profile in candidate_profiles:
            try:
                match_result = self._matcher_service.match(
                    ideal_profile=ideal_profile,
                    candidate_profile=candidate_profile,
                )
            except Exception as exc:
                error = BatchMatchError(
                    profile_url=candidate_profile.profile_url or candidate_profile.input_url,
                    username=candidate_profile.username or None,
                    error_type=type(exc).__name__,
                    error_message=_safe_error_message(exc),
                )
                errors.append(error)
                logger.warning(
                    "Batch blogger match failed: username=%s error_type=%s message=%s",
                    error.username or "-",
                    error.error_type,
                    error.error_message,
                )
                continue

            matches.append(match_result)

        result = BatchMatchResult(
            matches=_sort_matches(matches),
            errors=errors,
            total_candidates=len(candidate_profiles),
            successful_matches=len(matches),
            failed_matches=len(errors),
        )

        if not result.matches:
            raise BatchMatcherServiceError("Не удалось оценить ни одного кандидата.", result=result)

        return result


def _sort_matches(matches: list[BloggerMatchResult]) -> list[BloggerMatchResult]:
    decision_order = {
        MatchDecision.RECOMMENDED: 0,
        MatchDecision.REVIEW: 1,
        MatchDecision.REJECTED: 2,
    }
    return sorted(
        matches,
        key=lambda match: (
            decision_order[match.decision],
            -match.final_score,
            (match.username or "").casefold(),
            match.profile_url,
        ),
    )


def _safe_error_message(exc: Exception) -> str:
    message = " ".join(str(exc).split()) or "Unknown technical error."
    message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.IGNORECASE)
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-[redacted]", message)
    message = re.sub(r"(api[_-]?key=)[^\s&]+", r"\1[redacted]", message, flags=re.IGNORECASE)
    return message[:300]
