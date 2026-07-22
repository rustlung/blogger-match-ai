from __future__ import annotations

import pytest

from src.models.batch_match_result import BatchMatchResult
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.batch_matcher_service import BatchMatcherService, BatchMatcherServiceError
from src.services.llm_service import LLMServiceError


def test_batch_matcher_calls_matcher_for_each_candidate() -> None:
    ideal_profile = _ideal_profile()
    first = _blogger("first")
    second = _blogger("second")
    matcher = _matcher([_match_result("first"), _match_result("second")])

    result = BatchMatcherService(matcher_service=matcher).match_candidates(
        ideal_profile=ideal_profile,
        candidate_profiles=[first, second],
    )

    assert matcher.calls == [(ideal_profile, first), (ideal_profile, second)]
    assert result.successful_matches == 2


def test_batch_matcher_passes_same_ideal_profile_to_every_call() -> None:
    ideal_profile = _ideal_profile()
    matcher = _matcher([_match_result("first"), _match_result("second")])

    BatchMatcherService(matcher_service=matcher).match_candidates(
        ideal_profile=ideal_profile,
        candidate_profiles=[_blogger("first"), _blogger("second")],
    )

    assert all(call[0] is ideal_profile for call in matcher.calls)


def test_batch_matcher_collects_successful_match_results() -> None:
    first_match = _match_result("first")
    second_match = _match_result("second")
    matcher = _matcher([first_match, second_match])

    result = BatchMatcherService(matcher_service=matcher).match_candidates(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("first"), _blogger("second")],
    )

    assert result.matches == [first_match, second_match]
    assert result.errors == []


def test_batch_matcher_continues_after_one_candidate_error() -> None:
    matcher = _matcher([_match_result("first"), LLMServiceError("LLM unavailable."), _match_result("third")])

    result = BatchMatcherService(matcher_service=matcher).match_candidates(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("first"), _blogger("broken"), _blogger("third")],
    )

    assert [match.username for match in result.matches] == ["first", "third"]
    assert result.errors[0].username == "broken"
    assert result.total_candidates == 3
    assert result.successful_matches == 2
    assert result.failed_matches == 1


def test_batch_matcher_records_technical_error_without_rejected_match() -> None:
    matcher = _matcher([LLMServiceError("LLM timeout.")])

    with pytest.raises(BatchMatcherServiceError) as exc_info:
        BatchMatcherService(matcher_service=matcher).match_candidates(
            ideal_profile=_ideal_profile(),
            candidate_profiles=[_blogger("broken")],
        )

    result = exc_info.value.result
    assert isinstance(result, BatchMatchResult)
    assert result.matches == []
    assert result.errors[0].error_type == "LLMServiceError"
    assert "rejected" not in result.errors[0].model_dump(mode="json").values()


def test_batch_matcher_sorts_results_by_decision_score_and_username() -> None:
    matcher = _matcher(
        [
            _match_result("zeta", final_score=90, decision=MatchDecision.REVIEW),
            _match_result("beta", final_score=80, decision=MatchDecision.RECOMMENDED),
            _match_result("alpha", final_score=80, decision=MatchDecision.RECOMMENDED),
            _match_result("omega", final_score=0, decision=MatchDecision.REJECTED),
        ]
    )

    result = BatchMatcherService(matcher_service=matcher).match_candidates(
        ideal_profile=_ideal_profile(),
        candidate_profiles=[_blogger("zeta"), _blogger("beta"), _blogger("alpha"), _blogger("omega")],
    )

    assert [match.username for match in result.matches] == ["alpha", "beta", "zeta", "omega"]


def test_batch_matcher_does_not_call_matcher_for_empty_candidates() -> None:
    matcher = _matcher([])

    with pytest.raises(BatchMatcherServiceError, match="Нет кандидатов"):
        BatchMatcherService(matcher_service=matcher).match_candidates(
            ideal_profile=_ideal_profile(),
            candidate_profiles=[],
        )

    assert matcher.calls == []


def test_batch_matcher_raises_without_successful_result_when_all_candidates_fail() -> None:
    matcher = _matcher([RuntimeError("first failed"), RuntimeError("second failed")])

    with pytest.raises(BatchMatcherServiceError, match="ни одного кандидата") as exc_info:
        BatchMatcherService(matcher_service=matcher).match_candidates(
            ideal_profile=_ideal_profile(),
            candidate_profiles=[_blogger("first"), _blogger("second")],
        )

    result = exc_info.value.result
    assert isinstance(result, BatchMatchResult)
    assert result.total_candidates == 2
    assert result.successful_matches == 0
    assert result.failed_matches == 2


def _ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(
        niche="лайфстайл",
        min_followers=1000,
        required_topics=["семья"],
    )


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        biography="Short bio",
        followers_count=5000,
        raw_data={"username": username},
    )


def _match_result(
    username: str,
    *,
    final_score: int = 80,
    decision: MatchDecision = MatchDecision.RECOMMENDED,
) -> BloggerMatchResult:
    region_status = RegionStatus.TARGET
    rejection_reasons: list[str] = []
    detected_region: str | None = "Россия"
    region_confidence = 80
    if decision == MatchDecision.REJECTED:
        final_score = 0
        region_status = RegionStatus.NON_TARGET
        detected_region = "Украина"
        region_confidence = 90
        rejection_reasons = ["Не целевой регион."]
    elif decision == MatchDecision.REVIEW:
        region_status = RegionStatus.UNKNOWN
        detected_region = None
        region_confidence = 20

    return BloggerMatchResult(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        final_score=final_score,
        decision=decision,
        region_status=region_status,
        region_confidence=region_confidence,
        detected_region=detected_region,
        strengths=["Тематика совпадает."],
        risks=[],
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


def _matcher(results: list[BloggerMatchResult | Exception]):
    class FakeMatcherService:
        def __init__(self) -> None:
            self.calls: list[tuple[IdealBloggerProfile, BloggerProfile]] = []
            self._results = list(results)

        def match(
            self,
            ideal_profile: IdealBloggerProfile,
            candidate_profile: BloggerProfile,
        ) -> BloggerMatchResult:
            self.calls.append((ideal_profile, candidate_profile))
            result = self._results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    return FakeMatcherService()
