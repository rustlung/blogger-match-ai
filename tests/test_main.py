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
from src.models.discovery import DiscoveryCandidate, DiscoveryResult
from src.models.failed_profile import FailedProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.services.discovery_service import DiscoveryServiceError
from src.services.ideal_profile_service import IdealProfileServiceError


def test_main_builds_ideal_profile_from_reference_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_profile = _blogger("first")
    second_profile = _blogger("second")
    third_profile = _blogger("third")
    output_path = tmp_path / "ideal_blogger_profile.json"
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[first_profile, second_profile, third_profile]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=3),
        output_path=output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert len(state.ideal_profile_instances) == 1
    assert state.ideal_profile_instances[0].calls == [[first_profile, second_profile, third_profile]]
    assert state.matcher_instances == []
    assert payload["summary"] == {
        "profiles_requested": 3,
        "profiles_analyzed": 3,
        "apify_failures": 0,
    }
    assert payload["profile_analysis"]["ideal_profile"]["niche"] == "лайфстайл и бьюти"
    assert "Ideal blogger profile created." in output
    assert "Ideal blogger profile saved to results/ideal_blogger_profile.json" in output
    assert "Candidate:" not in output
    assert len(state.discovery_instances) == 1
    assert state.apify_load_calls == [
        [
            "https://www.instagram.com/first/",
            "https://www.instagram.com/second/",
            "https://www.instagram.com/third/",
        ],
        ["https://www.instagram.com/new_creator/"],
    ]
    assert state.discovery_instances[0].calls == [
        (
            _ideal_profile_analysis(source_profiles_count=3).ideal_profile,
            {"first", "second", "third"},
        )
    ]


def test_main_builds_profile_from_partial_apify_success_and_saves_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    blogger = _blogger("valid")
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
        error_description="Profile not found",
    )
    output_path = tmp_path / "ideal_blogger_profile.json"
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[blogger], failed_profiles=[failed_profile]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        output_path=output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert state.ideal_profile_instances[0].calls == [[blogger]]
    assert payload["summary"]["profiles_analyzed"] == 1
    assert payload["summary"]["apify_failures"] == 1
    assert payload["apify_failures"] == [failed_profile.model_dump(mode="json")]
    assert "Warning: reference sample is small" in output


def test_main_returns_error_when_only_apify_profile_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "ideal_blogger_profile.json"
    state = _patch_pipeline(
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
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        output_path=output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert state.ideal_profile_instances == []
    assert not output_path.exists()
    assert "нет успешных эталонных профилей" in output


def test_main_returns_error_when_ideal_profile_service_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "ideal_blogger_profile.json"
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_error=IdealProfileServiceError("Ideal profile LLM request timed out."),
        output_path=output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert len(state.ideal_profile_instances) == 1
    assert not output_path.exists()
    assert "Ошибка: Ideal profile LLM request timed out." in output


def test_main_returns_error_when_ideal_profile_results_cannot_be_saved(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        save_error=main_module.IdealProfileResultsSaveError("Не удалось сохранить портрет идеального блогера."),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Ошибка: Не удалось сохранить портрет идеального блогера." in output


def test_main_one_profile_warns_but_completes_when_service_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "ideal_blogger_profile.json"
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("single")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        output_path=output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert len(state.ideal_profile_instances[0].calls) == 1
    assert "Warning: reference sample is small" in output
    assert any(
        "Выборка содержит только 1 профиль" in limitation
        for limitation in payload["profile_analysis"]["data_limitations"]
    )


def test_main_does_not_create_candidate_analysis_results_for_reference_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    ideal_output_path = tmp_path / "ideal_blogger_profile.json"
    analysis_output_path = tmp_path / "analysis_results.json"
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        output_path=ideal_output_path,
        analysis_output_path=analysis_output_path,
    )

    exit_code = main_module.main()

    assert exit_code == 0
    assert ideal_output_path.exists()
    assert not analysis_output_path.exists()
    assert state.matcher_instances == []


def test_main_saves_discovered_candidates_after_ideal_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    discovery_output_path = tmp_path / "discovered_candidates.json"
    discovery_result = _discovery_result()
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        discovery_result=discovery_result,
        discovery_output_path=discovery_output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out
    payload = json.loads(discovery_output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload == discovery_result.model_dump(mode="json")
    assert "Discovery search queries: 1" in output
    assert "Discovered unique candidates: 1" in output
    assert "Discovered candidates saved to results/discovered_candidates.json" in output
    assert "Discovered profiles saved to results/discovered_profiles.json" in output


def test_main_saves_discovered_profiles_after_discovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    discovered_profiles_output_path = tmp_path / "discovered_profiles.json"
    candidate_profile = _blogger("new_creator")
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("reference")]),
        candidate_apify_result=ApifyEnrichmentResult(profiles=[candidate_profile]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        discovered_profiles_output_path=discovered_profiles_output_path,
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out
    payload = json.loads(discovered_profiles_output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["profiles"][0]["username"] == "new_creator"
    assert payload["total_profiles"] == 1
    assert payload["failed_profiles_count"] == 0
    assert "raw_data" not in payload["profiles"][0]
    assert "Candidate URLs found: 1" in output
    assert "Candidate profiles loaded successfully: 1" in output
    assert "Candidate profile load errors: 0" in output


def test_main_returns_error_when_discovered_profiles_cannot_be_saved(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("reference")]),
        candidate_apify_result=ApifyEnrichmentResult(profiles=[_blogger("candidate")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        discovered_profiles_save_error=main_module.DiscoveredProfilesSaveError("Не удалось сохранить найденные профили."),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Ошибка: Не удалось сохранить найденные профили." in output


def test_main_returns_error_when_discovery_configuration_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        settings=_settings(brave_search_api_key=""),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert state.discovery_instances == []
    assert "BRAVE_SEARCH_API_KEY не задан" in output


def test_main_returns_error_when_discovery_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        discovery_error=DiscoveryServiceError("Не удалось выполнить ни один поисковый запрос Brave Search."),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert len(state.discovery_instances) == 1
    assert "Ошибка: Не удалось выполнить ни один поисковый запрос Brave Search." in output


def test_main_returns_error_when_discovery_results_cannot_be_saved(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_pipeline(
        monkeypatch,
        apify_result=ApifyEnrichmentResult(profiles=[_blogger("creator")]),
        profile_analysis=_ideal_profile_analysis(source_profiles_count=1),
        discovery_save_error=main_module.DiscoveryResultsSaveError("Не удалось сохранить найденных кандидатов."),
    )

    exit_code = main_module.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Ошибка: Не удалось сохранить найденных кандидатов." in output


def test_build_ideal_blogger_profile_returns_mvp_profile_with_independent_lists() -> None:
    first_profile = main_module.build_ideal_blogger_profile()
    second_profile = main_module.build_ideal_blogger_profile()

    first_profile.required_topics.append("temporary-test-topic")

    assert isinstance(first_profile, IdealBloggerProfile)
    assert first_profile.niche == "general lifestyle"
    assert first_profile.required_brand_style == "authentic, brand-safe, non-controversial content"
    assert second_profile.required_topics == []
    assert first_profile.required_topics is not second_profile.required_topics


def test_save_analysis_results_still_excludes_raw_data(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "analysis_results.json"
    blogger = _blogger("creator")
    candidate = AnalyzedCandidate(
        blogger=blogger,
        analysis=_candidate_analysis(recommendation="Подходит"),
    )
    monkeypatch.setattr(main_module, "_generated_at", lambda: "2026-07-22T17:00:27+04:00")

    main_module.save_analysis_results(
        analyzed_candidates=[candidate],
        apify_failures=[],
        analysis_failures=[],
        summary={
            "profiles_received_from_apify": 1,
            "apify_failures": 0,
            "sent_to_llm": 1,
            "analyzed_successfully": 1,
            "llm_failures": 0,
        },
        output_path=output_path,
    )

    raw_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)

    assert payload["analyzed_candidates"][0]["analysis"]["recommendation"] == "Подходит"
    assert "raw_data" not in payload["analyzed_candidates"][0]["blogger"]
    assert "\\u041f" not in raw_text


def test_save_ideal_profile_results_creates_valid_json_without_raw_data(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "results" / "ideal_blogger_profile.json"
    failed_profile = FailedProfile(input_url="https://www.instagram.com/missing/", error_code="not_found")
    monkeypatch.setattr(main_module, "_generated_at", lambda: "2026-07-22T18:00:00+04:00")

    main_module.save_ideal_profile_results(
        profile_analysis=_ideal_profile_analysis(source_profiles_count=2),
        apify_failures=[failed_profile],
        summary={"profiles_requested": 3, "profiles_analyzed": 2, "apify_failures": 1},
        output_path=output_path,
    )

    raw_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)

    assert output_path.is_file()
    assert payload["generated_at"] == "2026-07-22T18:00:00+04:00"
    assert payload["summary"]["profiles_analyzed"] == 2
    assert payload["profile_analysis"]["ideal_profile"]["niche"] == "лайфстайл и бьюти"
    assert payload["apify_failures"] == [failed_profile.model_dump(mode="json")]
    assert "raw_data" not in raw_text
    assert "prompt" not in raw_text.lower()
    assert "api_key" not in raw_text.lower()
    assert "\\u043b" not in raw_text


def test_save_ideal_profile_results_creates_parent_directory(tmp_path) -> None:
    output_path = tmp_path / "nested" / "results" / "ideal_blogger_profile.json"

    main_module.save_ideal_profile_results(
        profile_analysis=_ideal_profile_analysis(),
        apify_failures=[],
        summary={"profiles_requested": 1, "profiles_analyzed": 1, "apify_failures": 0},
        output_path=output_path,
    )

    assert output_path.exists()


def test_save_ideal_profile_results_replaces_existing_file(tmp_path) -> None:
    output_path = tmp_path / "ideal_blogger_profile.json"

    main_module.save_ideal_profile_results(
        profile_analysis=_ideal_profile_analysis(niche="old"),
        apify_failures=[],
        summary={"profiles_requested": 1, "profiles_analyzed": 1, "apify_failures": 0},
        output_path=output_path,
    )
    main_module.save_ideal_profile_results(
        profile_analysis=_ideal_profile_analysis(niche="new"),
        apify_failures=[],
        summary={"profiles_requested": 1, "profiles_analyzed": 1, "apify_failures": 0},
        output_path=output_path,
    )

    raw_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)

    assert payload["profile_analysis"]["ideal_profile"]["niche"] == "new"
    assert "old" not in raw_text


def test_save_ideal_profile_results_removes_temp_file_on_write_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "ideal_blogger_profile.json"

    def fail_write(*args: Any, **kwargs: Any) -> None:
        raise main_module.AtomicJsonWriteError("disk full")

    monkeypatch.setattr(main_module, "atomic_write_json", fail_write)

    with pytest.raises(main_module.IdealProfileResultsSaveError):
        main_module.save_ideal_profile_results(
            profile_analysis=_ideal_profile_analysis(),
            apify_failures=[],
            summary={"profiles_requested": 1, "profiles_analyzed": 1, "apify_failures": 0},
            output_path=output_path,
        )

    assert not output_path.exists()
    assert not output_path.with_name("ideal_blogger_profile.json.tmp").exists()


def test_save_discovery_results_creates_serializable_json(tmp_path) -> None:
    output_path = tmp_path / "discovered_candidates.json"
    discovery_result = _discovery_result()

    main_module.save_discovery_results(discovery_result, output_path=output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload == discovery_result.model_dump(mode="json")


def test_save_discovered_profiles_creates_serializable_json_without_raw_data(tmp_path) -> None:
    output_path = tmp_path / "discovered_profiles.json"
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
    )

    main_module.save_discovered_profiles(
        ApifyEnrichmentResult(
            profiles=[_blogger("candidate")],
            failed_profiles=[failed_profile],
        ),
        output_path=output_path,
    )

    raw_text = output_path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)

    assert payload["profiles"][0]["username"] == "candidate"
    assert "raw_data" not in payload["profiles"][0]
    assert payload["failed_profiles"] == [failed_profile.model_dump(mode="json")]
    assert payload["total_profiles"] == 1
    assert payload["failed_profiles_count"] == 1


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    apify_result: ApifyEnrichmentResult,
    candidate_apify_result: ApifyEnrichmentResult | None = None,
    profile_analysis: IdealProfileAnalysis | None = None,
    profile_error: Exception | None = None,
    discovery_result: DiscoveryResult | None = None,
    discovery_error: Exception | None = None,
    settings: SimpleNamespace | None = None,
    output_path=None,
    analysis_output_path=None,
    discovery_output_path=None,
    discovered_profiles_output_path=None,
    save_error: Exception | None = None,
    discovery_save_error: Exception | None = None,
    discovered_profiles_save_error: Exception | None = None,
) -> SimpleNamespace:
    state = SimpleNamespace(
        apify_load_calls=[],
        ideal_profile_instances=[],
        matcher_instances=[],
        discovery_instances=[],
    )

    class FakeSheetsService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def get_instagram_urls(self) -> list[str]:
            return [
                "https://www.instagram.com/first/",
                "https://www.instagram.com/second/",
                "https://www.instagram.com/third/",
            ]

    class FakeApifyService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        def load_profiles(self, profile_urls: list[str]) -> ApifyEnrichmentResult:
            state.apify_profile_urls = profile_urls
            state.apify_load_calls.append(profile_urls)
            if len(state.apify_load_calls) == 1:
                return apify_result
            return candidate_apify_result or ApifyEnrichmentResult()

        def enrich_profiles(self, profile_urls: list[str]) -> ApifyEnrichmentResult:
            return self.load_profiles(profile_urls)

    class FakeIdealProfilePromptBuilder:
        pass

    class FakeIdealProfileService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.calls: list[list[BloggerProfile]] = []
            state.ideal_profile_instances.append(self)

        def build_ideal_profile(self, profiles: list[BloggerProfile]) -> IdealProfileAnalysis:
            self.calls.append(profiles)
            if profile_error is not None:
                raise profile_error
            assert profile_analysis is not None
            return profile_analysis

    class FakeMatcherService:
        def __init__(self, **kwargs: Any) -> None:
            state.matcher_instances.append(self)

    class FakeDiscoveryQueryBuilder:
        pass

    class FakeBraveSearchClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class FakeDiscoveryService:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.calls: list[tuple[IdealBloggerProfile, set[str]]] = []
            state.discovery_instances.append(self)

        def discover(
            self,
            ideal_profile: IdealBloggerProfile,
            reference_usernames: set[str],
        ) -> DiscoveryResult:
            self.calls.append((ideal_profile, reference_usernames))
            if discovery_error is not None:
                raise discovery_error
            return discovery_result or _discovery_result()

    monkeypatch.setattr(main_module, "settings", settings or _settings())
    monkeypatch.setattr(main_module, "SheetsService", FakeSheetsService)
    monkeypatch.setattr(main_module, "ApifyService", FakeApifyService)
    monkeypatch.setattr(main_module, "IdealProfilePromptBuilder", FakeIdealProfilePromptBuilder)
    monkeypatch.setattr(main_module, "IdealProfileService", FakeIdealProfileService)
    monkeypatch.setattr(main_module, "MatcherService", FakeMatcherService, raising=False)
    monkeypatch.setattr(main_module, "DiscoveryQueryBuilder", FakeDiscoveryQueryBuilder)
    monkeypatch.setattr(main_module, "BraveSearchClient", FakeBraveSearchClient)
    monkeypatch.setattr(main_module, "DiscoveryService", FakeDiscoveryService)

    original_save_ideal_profile_results = main_module.save_ideal_profile_results

    def fake_save_ideal_profile_results(**kwargs: Any) -> None:
        if save_error is not None:
            raise save_error
        if output_path is not None:
            kwargs["output_path"] = output_path
            original_save_ideal_profile_results(**kwargs)

    monkeypatch.setattr(main_module, "save_ideal_profile_results", fake_save_ideal_profile_results)

    original_save_discovery_results = main_module.save_discovery_results

    def fake_save_discovery_results(discovery_result: DiscoveryResult, output_path=main_module.DISCOVERED_CANDIDATES_PATH) -> None:
        if discovery_save_error is not None:
            raise discovery_save_error
        if discovery_output_path is not None:
            output_path = discovery_output_path
            original_save_discovery_results(discovery_result, output_path=output_path)

    monkeypatch.setattr(main_module, "save_discovery_results", fake_save_discovery_results)

    original_save_discovered_profiles = main_module.save_discovered_profiles

    def fake_save_discovered_profiles(enrichment_result: ApifyEnrichmentResult, output_path=main_module.DISCOVERED_PROFILES_PATH) -> None:
        if discovered_profiles_save_error is not None:
            raise discovered_profiles_save_error
        if discovered_profiles_output_path is not None:
            output_path = discovered_profiles_output_path
            original_save_discovered_profiles(enrichment_result, output_path=output_path)

    monkeypatch.setattr(main_module, "save_discovered_profiles", fake_save_discovered_profiles)

    if analysis_output_path is not None:
        original_save_analysis_results = main_module.save_analysis_results

        def fake_save_analysis_results(**kwargs: Any) -> None:
            kwargs["output_path"] = analysis_output_path
            original_save_analysis_results(**kwargs)

        monkeypatch.setattr(main_module, "save_analysis_results", fake_save_analysis_results)

    return state


def _settings(
    openai_api_key: str | None = "test-openai-key",
    brave_search_api_key: str = "test-brave-key",
) -> SimpleNamespace:
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
        BRAVE_SEARCH_API_KEY=brave_search_api_key,
    )


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        full_name=f"{username} name",
        biography="Short bio",
        followers_count=1000,
        follows_count=100,
        posts_count=20,
        verified=False,
        private=False,
        business_account=True,
        business_category_name="Digital creator",
        external_url=None,
        public_email=None,
        public_phone_number=None,
        profile_pic_url="https://images.example/avatar.jpg",
        raw_data={"username": username},
    )


def _ideal_profile_analysis(source_profiles_count: int = 1, niche: str = "лайфстайл и бьюти") -> IdealProfileAnalysis:
    return IdealProfileAnalysis(
        ideal_profile=IdealBloggerProfile(
            niche=niche,
            min_followers=1000,
            max_followers=10000,
            required_topics=["лайфстайл", "бьюти"],
            required_brand_style="безопасный и естественный стиль",
        ),
        source_profiles_count=source_profiles_count,
        common_traits=["Регулярно пишут о повседневном стиле"],
        important_selection_criteria=["Ясная ниша", "Безопасная коммуникация"],
        observed_variations=["Размер аудитории отличается"],
        data_limitations=[],
        explanation="Портрет построен по доступным данным профилей.",
        confidence=60.0,
    )


def _candidate_analysis(recommendation: str = "Suitable") -> CandidateAnalysis:
    return CandidateAnalysis(
        overall_score=82.0,
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


def _discovery_result() -> DiscoveryResult:
    return DiscoveryResult(
        queries=['site:instagram.com "бьюти" блогер Россия'],
        candidates=[
            DiscoveryCandidate(
                username="new_creator",
                profile_url="https://www.instagram.com/new_creator/",
                source_query='site:instagram.com "бьюти" блогер Россия',
                title="New Creator",
                description="Описание на русском",
            )
        ],
        total_candidates=1,
    )
