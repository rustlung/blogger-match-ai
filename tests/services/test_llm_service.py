from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.models.candidate_analysis import CandidateAnalysis
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.services import llm_service
from src.services.llm_service import LLMService, LLMServiceError


def test_analyze_candidate_returns_parsed_candidate_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = _analysis()
    fake_openai = _fake_openai_factory(_completion(parsed=analysis))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService(
        api_key="test-key",
        base_url="https://example.test/openai/v1",
        model="test-model",
        timeout=30,
    )

    result = service.analyze_candidate("system prompt", "user prompt")

    assert result is analysis
    assert len(fake_openai.instances) == 1
    parse_calls = fake_openai.instances[0].chat.completions.parse_calls
    assert len(parse_calls) == 1
    assert parse_calls[0]["model"] == "test-model"
    assert parse_calls[0]["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]
    assert parse_calls[0]["response_format"] is CandidateAnalysis


def test_analyze_candidate_raises_error_when_model_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=None, refusal="Cannot comply."))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService("test-key", "https://example.test", "test-model", 30)

    with pytest.raises(LLMServiceError, match="refused"):
        service.analyze_candidate("system prompt", "user prompt")


def test_analyze_candidate_raises_error_when_structured_response_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=None, refusal=None))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService("test-key", "https://example.test", "test-model", 30)

    with pytest.raises(LLMServiceError, match="structured analysis"):
        service.analyze_candidate("system prompt", "user prompt")


@pytest.mark.parametrize(
    ("exception_name", "expected_message"),
    [
        ("APITimeoutError", "timed out"),
        ("APIConnectionError", "connection failed"),
        ("AuthenticationError", "authentication failed"),
        ("RateLimitError", "rate limit exceeded"),
        ("BadRequestError", "rejected the request"),
        ("APIError", "request failed"),
    ],
)
def test_analyze_candidate_converts_openai_sdk_errors_to_service_errors(
    monkeypatch: pytest.MonkeyPatch,
    exception_name: str,
    expected_message: str,
) -> None:
    exception_type = type(exception_name, (Exception,), {})
    monkeypatch.setattr(llm_service, exception_name, exception_type)
    fake_openai = _fake_openai_factory(exception=exception_type("sdk error"))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService("test-key", "https://example.test", "test-model", 30)

    with pytest.raises(LLMServiceError, match=expected_message):
        service.analyze_candidate("system prompt", "user prompt")


@pytest.mark.parametrize(
    ("api_key", "base_url", "model", "timeout", "system_prompt", "user_prompt", "expected_message"),
    [
        ("", "https://example.test", "test-model", 30, "system", "user", "OPENAI_API_KEY"),
        ("test-key", "", "test-model", 30, "system", "user", "OPENAI_BASE_URL"),
        ("test-key", "https://example.test", "", 30, "system", "user", "OPENAI_MODEL"),
        ("test-key", "https://example.test", "test-model", 0, "system", "user", "greater than 0"),
        ("test-key", "https://example.test", "test-model", 30, "", "user", "System prompt"),
        ("test-key", "https://example.test", "test-model", 30, "system", "", "User prompt"),
    ],
)
def test_analyze_candidate_validates_configuration_and_prompts_before_api_call(
    monkeypatch: pytest.MonkeyPatch,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
    system_prompt: str,
    user_prompt: str,
    expected_message: str,
) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=_analysis()))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService(api_key, base_url, model, timeout)

    with pytest.raises(LLMServiceError, match=expected_message):
        service.analyze_candidate(system_prompt, user_prompt)

    assert fake_openai.instances[0].chat.completions.parse_calls == []


def test_analyze_match_returns_parsed_blogger_match_result(monkeypatch: pytest.MonkeyPatch) -> None:
    match_result = _match_result()
    fake_openai = _fake_openai_factory(_completion(parsed=match_result))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService(
        api_key="test-key",
        base_url="https://example.test/openai/v1",
        model="test-model",
        timeout=30,
    )

    result = service.analyze_match("system prompt", "user prompt")

    assert result is match_result
    parse_calls = fake_openai.instances[0].chat.completions.parse_calls
    assert len(parse_calls) == 1
    assert parse_calls[0]["response_format"] is BloggerMatchResult


def test_analyze_match_raises_error_when_structured_result_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=None))
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService("test-key", "https://example.test", "test-model", 30)

    with pytest.raises(LLMServiceError, match="structured match result"):
        service.analyze_match("system prompt", "user prompt")


def test_analyze_match_converts_validation_error_to_technical_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_validation_error() -> None:
        _match_result(final_score=101)

    try:
        raise_validation_error()
    except Exception as exc:
        validation_error = exc
    else:
        raise AssertionError("Expected invalid match result to raise.")

    fake_openai = _fake_openai_factory(exception=validation_error)
    monkeypatch.setattr(llm_service, "OpenAI", fake_openai.class_)

    service = LLMService("test-key", "https://example.test", "test-model", 30)

    with pytest.raises(LLMServiceError, match="failed validation"):
        service.analyze_match("system prompt", "user prompt")


def _analysis() -> CandidateAnalysis:
    return CandidateAnalysis(
        overall_score=0.8,
        niche_match_score=0.9,
        audience_match_score=0.7,
        content_quality_score=0.8,
        brand_safety_score=0.95,
        recommendation="shortlist",
        explanation="Good candidate fit.",
        confidence=0.85,
    )


def _match_result(final_score: int = 82) -> BloggerMatchResult:
    return BloggerMatchResult(
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        final_score=final_score,
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


def _completion(parsed: CandidateAnalysis | None, refusal: str | None = None) -> Any:
    message = SimpleNamespace(parsed=parsed, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _fake_openai_factory(completion: Any | None = None, exception: Exception | None = None) -> Any:
    instances: list[Any] = []

    class FakeCompletions:
        def __init__(self) -> None:
            self.parse_calls: list[dict[str, Any]] = []

        def parse(self, **kwargs: Any) -> Any:
            self.parse_calls.append(kwargs)
            if exception is not None:
                raise exception
            return completion

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
            self.api_key = api_key
            self.base_url = base_url
            self.timeout = timeout
            self.chat = FakeChat()
            instances.append(self)

    return SimpleNamespace(class_=FakeOpenAI, instances=instances)
