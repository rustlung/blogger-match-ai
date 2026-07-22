from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.models.candidate_analysis import CandidateAnalysis
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.llm_service import LLMServiceError
from src.services.matcher_service import MatcherService


def test_match_candidate_coordinates_prompt_builder_and_llm_service() -> None:
    ideal_profile = _ideal_profile()
    blogger = _blogger_profile()
    candidate_analysis = _candidate_analysis()
    prompt_builder = Mock()
    llm_service = Mock()
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    llm_service.analyze_candidate.return_value = candidate_analysis

    result = MatcherService(prompt_builder, llm_service).match_candidate(
        ideal_profile=ideal_profile,
        blogger=blogger,
    )

    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_called_once_with(
        ideal_profile=ideal_profile,
        blogger=blogger,
    )
    llm_service.analyze_candidate.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )
    assert isinstance(result, AnalyzedCandidate)
    assert result.blogger == blogger
    assert result.analysis is candidate_analysis


def test_match_candidate_preserves_original_blogger_object() -> None:
    blogger = _blogger_profile()
    prompt_builder = Mock()
    llm_service = Mock()
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    llm_service.analyze_candidate.return_value = _candidate_analysis()

    result = MatcherService(prompt_builder, llm_service).match_candidate(
        ideal_profile=_ideal_profile(),
        blogger=blogger,
    )

    assert result.blogger is blogger


def test_match_candidate_propagates_prompt_builder_error_without_llm_call() -> None:
    prompt_builder = Mock()
    llm_service = Mock()
    prompt_builder.build_system_prompt.side_effect = RuntimeError("prompt failed")

    with pytest.raises(RuntimeError, match="prompt failed"):
        MatcherService(prompt_builder, llm_service).match_candidate(
            ideal_profile=_ideal_profile(),
            blogger=_blogger_profile(),
        )

    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_not_called()
    llm_service.analyze_candidate.assert_not_called()


def test_match_candidate_propagates_llm_service_error() -> None:
    ideal_profile = _ideal_profile()
    blogger = _blogger_profile()
    prompt_builder = Mock()
    llm_service = Mock()
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    llm_service.analyze_candidate.side_effect = LLMServiceError("LLM failed")

    with pytest.raises(LLMServiceError, match="LLM failed"):
        MatcherService(prompt_builder, llm_service).match_candidate(
            ideal_profile=ideal_profile,
            blogger=blogger,
        )

    prompt_builder.build_system_prompt.assert_called_once_with()
    prompt_builder.build_user_prompt.assert_called_once_with(
        ideal_profile=ideal_profile,
        blogger=blogger,
    )
    llm_service.analyze_candidate.assert_called_once_with(
        system_prompt="system prompt",
        user_prompt="user prompt",
    )


def test_match_candidate_passes_prompts_to_llm_service_not_domain_models() -> None:
    ideal_profile = _ideal_profile()
    blogger = _blogger_profile()
    prompt_builder = Mock()
    llm_service = Mock()
    prompt_builder.build_system_prompt.return_value = "system prompt"
    prompt_builder.build_user_prompt.return_value = "user prompt"
    llm_service.analyze_candidate.return_value = _candidate_analysis()

    MatcherService(prompt_builder, llm_service).match_candidate(
        ideal_profile=ideal_profile,
        blogger=blogger,
    )

    _, kwargs = llm_service.analyze_candidate.call_args
    assert kwargs == {
        "system_prompt": "system prompt",
        "user_prompt": "user prompt",
    }
    assert ideal_profile not in kwargs.values()
    assert blogger not in kwargs.values()


def test_match_coordinates_matcher_prompt_builder_and_llm_service() -> None:
    ideal_profile = _ideal_profile()
    blogger = _blogger_profile()
    match_result = _match_result()
    old_prompt_builder = Mock()
    matcher_prompt_builder = Mock()
    llm_service = Mock()
    matcher_prompt_builder.build_system_prompt.return_value = "matcher system"
    matcher_prompt_builder.build_user_prompt.return_value = "matcher user"
    llm_service.analyze_match.return_value = match_result

    result = MatcherService(
        old_prompt_builder,
        llm_service,
        matcher_prompt_builder=matcher_prompt_builder,
    ).match(
        ideal_profile=ideal_profile,
        candidate_profile=blogger,
    )

    matcher_prompt_builder.build_system_prompt.assert_called_once_with()
    matcher_prompt_builder.build_user_prompt.assert_called_once_with(
        ideal_profile=ideal_profile,
        candidate_profile=blogger,
    )
    llm_service.analyze_match.assert_called_once_with(
        system_prompt="matcher system",
        user_prompt="matcher user",
    )
    assert isinstance(result, BloggerMatchResult)
    assert result is match_result
    old_prompt_builder.build_system_prompt.assert_not_called()


def test_match_propagates_ai_technical_error_without_business_rejection() -> None:
    matcher_prompt_builder = Mock()
    llm_service = Mock()
    matcher_prompt_builder.build_system_prompt.return_value = "matcher system"
    matcher_prompt_builder.build_user_prompt.return_value = "matcher user"
    llm_service.analyze_match.side_effect = LLMServiceError("LLM match request timed out.")

    with pytest.raises(LLMServiceError, match="timed out"):
        MatcherService(
            Mock(),
            llm_service,
            matcher_prompt_builder=matcher_prompt_builder,
        ).match(
            ideal_profile=_ideal_profile(),
            candidate_profile=_blogger_profile(),
        )

    llm_service.analyze_match.assert_called_once()


def _ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(
        niche="beauty",
        min_followers=1000,
        required_topics=["skincare"],
    )


def _blogger_profile() -> BloggerProfile:
    return BloggerProfile(
        input_url="https://www.instagram.com/creator/",
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        full_name="Creator Name",
        biography="Helpful bio",
        followers_count=12000,
        raw_data={"username": "creator"},
    )


def _candidate_analysis() -> CandidateAnalysis:
    return CandidateAnalysis(
        overall_score=0.82,
        niche_match_score=0.9,
        audience_match_score=0.8,
        content_quality_score=0.75,
        brand_safety_score=0.95,
        recommendation="shortlist",
        explanation="Strong fit.",
        confidence=0.88,
    )


def _match_result() -> BloggerMatchResult:
    return BloggerMatchResult(
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        final_score=82,
        decision=MatchDecision.RECOMMENDED,
        region_status=RegionStatus.TARGET,
        region_confidence=80,
        detected_region="Россия",
        strengths=["Тематика совпадает."],
        risks=[],
        rejection_reasons=[],
        match_summary="Кандидат подходит.",
        criteria_scores=MatchCriteriaScores(
            thematic_fit=_criterion(90, 80),
            audience_fit=_criterion(70, 50),
            geography_fit=_criterion(85, 80),
            language_fit=_criterion(75, 60),
            account_size_fit=_criterion(80, 80),
            engagement_fit=_criterion(40, 20),
            content_style_fit=_criterion(85, 70),
            commercial_fit=_criterion(80, 70),
        ),
    )


def _criterion(score: int, confidence: int) -> MatchCriterionScore:
    return MatchCriterionScore(
        score=score,
        confidence=confidence,
        reason="Тестовая причина.",
    )
