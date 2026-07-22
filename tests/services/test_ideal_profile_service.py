from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.models.blogger import BloggerProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.services import ideal_profile_service
from src.services.ideal_profile_service import IdealProfileService, IdealProfileServiceError


def test_build_ideal_profile_returns_parsed_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = _analysis()
    fake_openai = _fake_openai_factory(_completion(parsed=analysis))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    prompt_builder = _prompt_builder()
    service = IdealProfileService(prompt_builder, "test-key", "https://example.test", "test-model", 30)

    result = service.build_ideal_profile([_blogger("first"), _blogger("second")])

    assert result is analysis
    assert prompt_builder.system_calls == 1
    assert prompt_builder.user_calls == [[_blogger("first"), _blogger("second")]]
    assert len(fake_openai.instances) == 1
    parse_calls = fake_openai.instances[0].chat.completions.parse_calls
    assert len(parse_calls) == 1
    assert parse_calls[0]["response_format"] is IdealProfileAnalysis
    assert parse_calls[0]["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]


def test_build_ideal_profile_uses_one_llm_call_for_multiple_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=_analysis(source_profiles_count=3)))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    service = IdealProfileService(_prompt_builder(), "test-key", "https://example.test", "test-model", 30)

    service.build_ideal_profile([_blogger("first"), _blogger("second"), _blogger("third")])

    assert len(fake_openai.instances) == 1
    assert len(fake_openai.instances[0].chat.completions.parse_calls) == 1


def test_build_ideal_profile_rejects_empty_profiles_before_api_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=_analysis()))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    service = IdealProfileService(_prompt_builder(), "test-key", "https://example.test", "test-model", 30)

    with pytest.raises(IdealProfileServiceError, match="empty"):
        service.build_ideal_profile([])

    assert fake_openai.instances[0].chat.completions.parse_calls == []


def test_build_ideal_profile_raises_error_when_model_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=None, refusal="Cannot comply."))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    service = IdealProfileService(_prompt_builder(), "test-key", "https://example.test", "test-model", 30)

    with pytest.raises(IdealProfileServiceError, match="refused") as exc_info:
        service.build_ideal_profile([_blogger("creator")])

    assert "Cannot comply" not in str(exc_info.value)


def test_build_ideal_profile_raises_error_when_parsed_result_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=None))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    service = IdealProfileService(_prompt_builder(), "test-key", "https://example.test", "test-model", 30)

    with pytest.raises(IdealProfileServiceError, match="structured ideal profile"):
        service.build_ideal_profile([_blogger("creator")])


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
def test_build_ideal_profile_converts_openai_sdk_errors_to_safe_service_errors(
    monkeypatch: pytest.MonkeyPatch,
    exception_name: str,
    expected_message: str,
) -> None:
    exception_type = type(exception_name, (Exception,), {})
    monkeypatch.setattr(ideal_profile_service, exception_name, exception_type)
    fake_openai = _fake_openai_factory(exception=exception_type("sdk error with prompt test-key"))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    service = IdealProfileService(_prompt_builder(), "test-key", "https://example.test", "test-model", 30)

    with pytest.raises(IdealProfileServiceError, match=expected_message) as exc_info:
        service.build_ideal_profile([_blogger("creator")])

    error_text = str(exc_info.value)
    assert "system prompt" not in error_text
    assert "user prompt" not in error_text
    assert "test-key" not in error_text


def test_build_ideal_profile_validates_configuration_and_prompts_before_api_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_openai = _fake_openai_factory(_completion(parsed=_analysis()))
    monkeypatch.setattr(ideal_profile_service, "OpenAI", fake_openai.class_)
    service = IdealProfileService(_prompt_builder(system_prompt=""), "test-key", "https://example.test", "test-model", 30)

    with pytest.raises(ValueError):
        service.build_ideal_profile([_blogger("creator")])

    assert fake_openai.instances[0].chat.completions.parse_calls == []


def _analysis(source_profiles_count: int = 2) -> IdealProfileAnalysis:
    return IdealProfileAnalysis(
        ideal_profile=IdealBloggerProfile(
            niche="лайфстайл",
            required_brand_style="спокойный и безопасный стиль",
        ),
        source_profiles_count=source_profiles_count,
        common_traits=["естественная коммуникация"],
        important_selection_criteria=["ясная ниша"],
        observed_variations=["разные размеры аудитории"],
        data_limitations=["нет данных Instagram Insights"],
        explanation="Портрет построен по выборке.",
        confidence=70.0,
    )


def _completion(parsed: IdealProfileAnalysis | None, refusal: str | None = None) -> Any:
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


def _prompt_builder(system_prompt: str = "system prompt", user_prompt: str = "user prompt") -> Any:
    class FakePromptBuilder:
        def __init__(self) -> None:
            self.system_calls = 0
            self.user_calls: list[list[BloggerProfile]] = []

        def build_system_prompt(self) -> str:
            self.system_calls += 1
            return system_prompt

        def build_user_prompt(self, profiles: list[BloggerProfile]) -> str:
            self.user_calls.append(profiles)
            if not system_prompt.strip():
                raise ValueError("system prompt is empty")
            return user_prompt

    return FakePromptBuilder()


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        full_name="Creator",
        biography="Bio",
        followers_count=1000,
        raw_data={"username": username},
    )
