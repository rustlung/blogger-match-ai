from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src import main as main_module
from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.blogger import BloggerProfile
from src.models.candidate_analysis import CandidateAnalysis
from src.models.failed_profile import FailedProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.llm_service import LLMServiceError


def test_main_runs_full_successful_pipeline(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    blogger = _blogger("creator")
    analysis = _analysis(overall_score=82.0, recommendation="Suitable")
    matcher_state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[blogger]),
        matcher_side_effects=[AnalyzedCandidate(blogger=blogger, analysis=analysis)],
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert matcher_state.instances[0].calls[0] == (_expected_ideal_profile(), blogger)
    assert "Overall score: 82.0" in output
    assert "Recommendation: Suitable" in output
    assert "Analyzed successfully: 1" in output


def test_main_sends_only_successful_apify_profiles_to_matcher(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    blogger = _blogger("valid")
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
        error_description="Post does not exist",
    )
    matcher_state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(
            profiles=[blogger],
            failed_profiles=[failed_profile],
        ),
        matcher_side_effects=[AnalyzedCandidate(blogger=blogger, analysis=_analysis())],
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert len(matcher_state.instances[0].calls) == 1
    assert matcher_state.instances[0].calls[0][1] is blogger
    assert "Apify failures: 1" in output
    assert "Failed: 1" in output


def test_main_skips_llm_when_all_apify_profiles_failed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    matcher_state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(
            failed_profiles=[
                FailedProfile(
                    input_url="https://www.instagram.com/missing/",
                    username="missing",
                    error_code="not_found",
                )
            ]
        ),
        matcher_side_effects=[],
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert matcher_state.instances == []
    assert "No successful Apify profiles available for AI analysis." in output
    assert "Sent to LLM: 0" in output


def test_main_continues_when_one_llm_analysis_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failed_blogger = _blogger("failed")
    successful_blogger = _blogger("success")
    matcher_state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[failed_blogger, successful_blogger]),
        matcher_side_effects=[
            LLMServiceError("LLM request timed out."),
            AnalyzedCandidate(blogger=successful_blogger, analysis=_analysis()),
        ],
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert len(matcher_state.instances[0].calls) == 2
    assert "Analyzed successfully: 1" in output
    assert "LLM failures: 1" in output
    assert "- failed — LLM request timed out." in output


def test_main_returns_error_when_all_llm_analyses_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_blogger = _blogger("first")
    second_blogger = _blogger("second")
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[first_blogger, second_blogger]),
        matcher_side_effects=[
            LLMServiceError("LLM request timed out."),
            LLMServiceError("LLM rate limit exceeded."),
        ],
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Analyzed successfully: 0" in output
    assert "LLM failures: 2" in output
    assert "LLM request timed out." in output
    assert "LLM rate limit exceeded." in output


def test_main_returns_configuration_error_without_llm_call_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    matcher_state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        matcher_side_effects=[],
        settings=_settings(openai_api_key=None),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert matcher_state.llm_instances == []
    assert matcher_state.instances == []
    assert "LLM configuration error: OPENAI_API_KEY is not configured." in output
    assert "secret" not in output.lower()


def test_build_ideal_blogger_profile_returns_mvp_profile_with_independent_lists() -> None:
    first_profile = main_module.build_ideal_blogger_profile()
    second_profile = main_module.build_ideal_blogger_profile()

    first_profile.required_topics.append("temporary-test-topic")

    assert isinstance(first_profile, IdealBloggerProfile)
    assert first_profile.niche == "general lifestyle"
    assert first_profile.required_brand_style == "authentic, brand-safe, non-controversial content"
    assert second_profile.required_topics == []
    assert first_profile.required_topics is not second_profile.required_topics


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    apify_result: ApifyEnrichmentResult,
    matcher_side_effects: list[Any],
    settings: SimpleNamespace | None = None,
) -> SimpleNamespace:
    state = SimpleNamespace(
        instances=[],
        llm_instances=[],
    )

    class FakeSheetsService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def get_instagram_urls(self) -> list[str]:
            return ["https://www.instagram.com/creator/"]

    class FakeApifyService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def enrich_profiles(self, profile_urls: list[str]) -> ApifyEnrichmentResult:
            return apify_result

    class FakePromptBuilder:
        pass

    class FakeLLMService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            state.llm_instances.append(self)

    class FakeMatcherService:
        def __init__(self, prompt_builder: FakePromptBuilder, llm_service: FakeLLMService) -> None:
            self.prompt_builder = prompt_builder
            self.llm_service = llm_service
            self.calls: list[tuple[IdealBloggerProfile, BloggerProfile]] = []
            self._side_effects = list(matcher_side_effects)
            state.instances.append(self)

        def match_candidate(
            self,
            ideal_profile: IdealBloggerProfile,
            blogger: BloggerProfile,
        ) -> AnalyzedCandidate:
            self.calls.append((ideal_profile, blogger))
            result = self._side_effects.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(main_module, "settings", settings or _settings())
    monkeypatch.setattr(main_module, "SheetsService", FakeSheetsService)
    monkeypatch.setattr(main_module, "ApifyService", FakeApifyService)
    monkeypatch.setattr(main_module, "PromptBuilder", FakePromptBuilder)
    monkeypatch.setattr(main_module, "LLMService", FakeLLMService)
    monkeypatch.setattr(main_module, "MatcherService", FakeMatcherService)

    return state


def _settings(openai_api_key: str | None = "test-openai-key") -> SimpleNamespace:
    return SimpleNamespace(
        GOOGLE_SERVICE_ACCOUNT_FILE="service_account.json",
        GOOGLE_SPREADSHEET_ID="spreadsheet-id",
        GOOGLE_SOURCE_SHEET="Input",
        GOOGLE_SOURCE_COLUMN="B",
        APIFY_SOURCE_PROFILES_LIMIT=3,
        APIFY_API_TOKEN="test-apify-token",
        APIFY_ACTOR_ID="apify~instagram-scraper",
        APIFY_REQUEST_TIMEOUT_SECONDS=300,
        openai_api_key=openai_api_key,
        openai_base_url="https://api.proxyapi.ru/openai/v1",
        openai_model="gpt-5-mini",
        openai_request_timeout_seconds=120,
    )


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        full_name=f"{username} name",
        biography="Short bio",
        followers_count=1000,
        raw_data={"username": username},
    )


def _analysis(overall_score: float = 82.0, recommendation: str = "Suitable") -> CandidateAnalysis:
    return CandidateAnalysis(
        overall_score=overall_score,
        niche_match_score=80.0,
        audience_match_score=75.0,
        content_quality_score=85.0,
        brand_safety_score=90.0,
        strengths=["Good audience fit"],
        weaknesses=["Limited public data"],
        recommendation=recommendation,
        explanation="Compact test explanation.",
        confidence=0.86,
    )


def _expected_ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(
        niche="general lifestyle",
        required_brand_style="authentic, brand-safe, non-controversial content",
    )
