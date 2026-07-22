from __future__ import annotations

from typing import Any

import pytest

from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.blogger import BloggerProfile
from src.models.discovery import DiscoveryCandidate, DiscoveryResult
from src.models.failed_profile import FailedProfile
from src.services.apify_service import ApifyServiceError
from src.services.discovered_profile_enrichment_service import (
    DiscoveredProfileEnrichmentService,
    DiscoveredProfileEnrichmentServiceError,
)


def test_enrichment_service_turns_discovery_result_into_profile_urls() -> None:
    loader = _profile_loader(ApifyEnrichmentResult(profiles=[_blogger("first")]))
    service = DiscoveredProfileEnrichmentService(profile_loader=loader)

    service.enrich_discovered_profiles(_discovery_result())

    assert loader.calls == [
        [
            "https://www.instagram.com/first/",
            "https://www.instagram.com/second/",
        ]
    ]


def test_enrichment_service_calls_load_profiles_once() -> None:
    loader = _profile_loader(ApifyEnrichmentResult(profiles=[_blogger("first")]))
    service = DiscoveredProfileEnrichmentService(profile_loader=loader)

    service.enrich_discovered_profiles(_discovery_result())

    assert len(loader.calls) == 1


def test_enrichment_service_returns_successes_and_profile_failures_without_interrupting() -> None:
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
    )
    service = DiscoveredProfileEnrichmentService(
        profile_loader=_profile_loader(
            ApifyEnrichmentResult(
                profiles=[_blogger("first")],
                failed_profiles=[failed_profile],
            )
        )
    )

    result = service.enrich_discovered_profiles(_discovery_result())

    assert [profile.username for profile in result.profiles] == ["first"]
    assert result.failed_profiles == [failed_profile]


def test_enrichment_service_returns_empty_result_without_apify_call_for_empty_discovery() -> None:
    loader = _profile_loader(ApifyEnrichmentResult())
    service = DiscoveredProfileEnrichmentService(profile_loader=loader)

    result = service.enrich_discovered_profiles(
        DiscoveryResult(queries=["q"], candidates=[], total_candidates=0)
    )

    assert result == ApifyEnrichmentResult()
    assert loader.calls == []


def test_enrichment_service_raises_clear_error_when_apify_fully_fails() -> None:
    service = DiscoveredProfileEnrichmentService(
        profile_loader=_profile_loader(ApifyServiceError("Apify unavailable."))
    )

    with pytest.raises(DiscoveredProfileEnrichmentServiceError, match="найденные профили"):
        service.enrich_discovered_profiles(_discovery_result())


def _profile_loader(result: ApifyEnrichmentResult | Exception) -> Any:
    class FakeProfileLoader:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def load_profiles(self, profile_urls: list[str]) -> ApifyEnrichmentResult:
            self.calls.append(profile_urls)
            if isinstance(result, Exception):
                raise result
            return result

    return FakeProfileLoader()


def _discovery_result() -> DiscoveryResult:
    return DiscoveryResult(
        queries=["q"],
        candidates=[
            DiscoveryCandidate(
                username="first",
                profile_url="https://www.instagram.com/first/",
                source_query="q",
            ),
            DiscoveryCandidate(
                username="second",
                profile_url="https://www.instagram.com/second/",
                source_query="q",
            ),
        ],
        total_candidates=2,
    )


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        raw_data={"username": username},
    )
