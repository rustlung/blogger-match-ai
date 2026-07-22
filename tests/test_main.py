from __future__ import annotations

import json
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


def test_main_creates_results_file_when_all_llm_analyses_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "analysis_results.json"
    first_blogger = _blogger("first")
    second_blogger = _blogger("second")
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[first_blogger, second_blogger]),
        matcher_side_effects=[
            LLMServiceError("LLM request timed out."),
            LLMServiceError("LLM rate limit exceeded."),
        ],
        output_path=output_path,
    )

    exit_code = main_module.main()
    capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["analyzed_candidates"] == []
    assert [failure["username"] for failure in payload["llm_failures"]] == ["first", "second"]
    assert payload["summary"]["llm_failures"] == 2


def test_build_ideal_blogger_profile_returns_mvp_profile_with_independent_lists() -> None:
    first_profile = main_module.build_ideal_blogger_profile()
    second_profile = main_module.build_ideal_blogger_profile()

    first_profile.required_topics.append("temporary-test-topic")

    assert isinstance(first_profile, IdealBloggerProfile)
    assert first_profile.niche == "general lifestyle"
    assert first_profile.required_brand_style == "authentic, brand-safe, non-controversial content"
    assert second_profile.required_topics == []
    assert first_profile.required_topics is not second_profile.required_topics


def test_save_analysis_results_creates_valid_json_without_raw_data(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "results" / "analysis_results.json"
    blogger = _blogger("creator")
    analyzed_candidate = AnalyzedCandidate(
        blogger=blogger,
        analysis=_analysis(
            recommendation="Подходит для тестовой интеграции",
            strengths=["Хорошее соответствие аудитории"],
        ),
    )
    monkeypatch.setattr(main_module, "_generated_at", lambda: "2026-07-22T17:00:27+04:00")

    main_module.save_analysis_results(
        analyzed_candidates=[analyzed_candidate],
        apify_failures=[],
        analysis_failures=[],
        summary=_summary(analyzed_successfully=1),
        output_path=output_path,
    )

    raw_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)

    assert output_path.is_file()
    assert payload["generated_at"] == "2026-07-22T17:00:27+04:00"
    assert payload["summary"]["analyzed_successfully"] == 1
    assert payload["analyzed_candidates"][0]["blogger"]["username"] == "creator"
    assert "raw_data" not in payload["analyzed_candidates"][0]["blogger"]
    assert "Подходит для тестовой интеграции" in raw_text
    assert "Хорошее соответствие аудитории" in raw_text
    assert "\\u041f" not in raw_text


def test_save_analysis_results_contains_successes_apify_failures_and_llm_failures(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "analysis_results.json"
    blogger = _blogger("creator")
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
        error_description="Post does not exist",
    )
    monkeypatch.setattr(main_module, "_generated_at", lambda: "2026-07-22T17:00:27+04:00")

    main_module.save_analysis_results(
        analyzed_candidates=[AnalyzedCandidate(blogger=blogger, analysis=_analysis())],
        apify_failures=[failed_profile],
        analysis_failures=[(_blogger("llm_failed"), "LLM request timed out.")],
        summary=_summary(analyzed_successfully=1, apify_failures=1, llm_failures=1),
        output_path=output_path,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(payload["analyzed_candidates"]) == 1
    assert payload["apify_failures"] == [failed_profile.model_dump(mode="json")]
    assert payload["llm_failures"] == [
        {
            "username": "llm_failed",
            "profile_url": "https://www.instagram.com/llm_failed/",
            "error": "LLM request timed out.",
        }
    ]
    assert payload["summary"]["apify_failures"] == 1
    assert payload["summary"]["llm_failures"] == 1


def test_save_analysis_results_handles_only_apify_failures(tmp_path) -> None:
    output_path = tmp_path / "analysis_results.json"
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
    )

    main_module.save_analysis_results(
        analyzed_candidates=[],
        apify_failures=[failed_profile],
        analysis_failures=[],
        summary=_summary(
            profiles_received_from_apify=0,
            apify_failures=1,
            sent_to_llm=0,
            analyzed_successfully=0,
            llm_failures=0,
        ),
        output_path=output_path,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["analyzed_candidates"] == []
    assert payload["apify_failures"][0]["username"] == "missing"
    assert payload["summary"]["profiles_received_from_apify"] == 0
    assert payload["summary"]["apify_failures"] == 1


def test_save_analysis_results_creates_parent_directory(tmp_path) -> None:
    output_path = tmp_path / "nested" / "results" / "analysis_results.json"

    main_module.save_analysis_results(
        analyzed_candidates=[],
        apify_failures=[],
        analysis_failures=[],
        summary=_summary(),
        output_path=output_path,
    )

    assert output_path.is_file()


def test_save_analysis_results_removes_temp_file_on_write_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "analysis_results.json"

    def fail_dump(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(main_module.json, "dump", fail_dump)

    with pytest.raises(main_module.AnalysisResultsSaveError):
        main_module.save_analysis_results(
            analyzed_candidates=[],
            apify_failures=[],
            analysis_failures=[],
            summary=_summary(),
            output_path=output_path,
        )

    assert not output_path.exists()
    assert not output_path.with_name("analysis_results.json.tmp").exists()


def test_main_returns_error_when_analysis_results_cannot_be_saved(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    blogger = _blogger("creator")
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[blogger]),
        matcher_side_effects=[AnalyzedCandidate(blogger=blogger, analysis=_analysis())],
        save_error=main_module.AnalysisResultsSaveError("Не удалось сохранить результаты анализа."),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Ошибка: Не удалось сохранить результаты анализа." in output


def test_save_analysis_results_replaces_existing_file(tmp_path) -> None:
    output_path = tmp_path / "analysis_results.json"
    first_candidate = AnalyzedCandidate(blogger=_blogger("old"), analysis=_analysis())
    second_candidate = AnalyzedCandidate(blogger=_blogger("new"), analysis=_analysis())

    main_module.save_analysis_results(
        analyzed_candidates=[first_candidate],
        apify_failures=[],
        analysis_failures=[],
        summary=_summary(analyzed_successfully=1),
        output_path=output_path,
    )
    main_module.save_analysis_results(
        analyzed_candidates=[second_candidate],
        apify_failures=[],
        analysis_failures=[],
        summary=_summary(analyzed_successfully=1),
        output_path=output_path,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(payload["analyzed_candidates"]) == 1
    assert payload["analyzed_candidates"][0]["blogger"]["username"] == "new"
    assert "old" not in output_path.read_text(encoding="utf-8")


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    apify_result: ApifyEnrichmentResult,
    matcher_side_effects: list[Any],
    settings: SimpleNamespace | None = None,
    output_path=None,
    save_error: Exception | None = None,
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
    original_save_analysis_results = main_module.save_analysis_results

    def fake_save_analysis_results(**kwargs: Any) -> None:
        if save_error is not None:
            raise save_error
        if output_path is not None:
            kwargs["output_path"] = output_path
            original_save_analysis_results(**kwargs)

    monkeypatch.setattr(main_module, "save_analysis_results", fake_save_analysis_results)

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


def _analysis(
    overall_score: float = 82.0,
    recommendation: str = "Suitable",
    strengths: list[str] | None = None,
) -> CandidateAnalysis:
    return CandidateAnalysis(
        overall_score=overall_score,
        niche_match_score=80.0,
        audience_match_score=75.0,
        content_quality_score=85.0,
        brand_safety_score=90.0,
        strengths=strengths or ["Good audience fit"],
        weaknesses=["Limited public data"],
        recommendation=recommendation,
        explanation="Compact test explanation.",
        confidence=0.86,
    )


def _summary(
    profiles_received_from_apify: int = 1,
    apify_failures: int = 0,
    sent_to_llm: int = 1,
    analyzed_successfully: int = 0,
    llm_failures: int = 0,
) -> dict[str, int]:
    return {
        "profiles_received_from_apify": profiles_received_from_apify,
        "apify_failures": apify_failures,
        "sent_to_llm": sent_to_llm,
        "analyzed_successfully": analyzed_successfully,
        "llm_failures": llm_failures,
    }


def _expected_ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(
        niche="general lifestyle",
        required_brand_style="authentic, brand-safe, non-controversial content",
    )
