from __future__ import annotations

from typing import Any

import pytest

from src.models.discovery import DiscoveryResult
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.brave_search_client import BraveSearchClientError
from src.services.discovery_query_builder import DiscoveryQueryBuilder
from src.services.discovery_service import (
    DiscoveryService,
    DiscoveryServiceError,
    normalize_instagram_profile_url,
    reference_usernames_from_urls,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.instagram.com/username/", ("username", "https://www.instagram.com/username/")),
        ("https://instagram.com/User.Name_123", ("user.name_123", "https://www.instagram.com/user.name_123/")),
        ("http://www.instagram.com/username/?utm=1", ("username", "https://www.instagram.com/username/")),
        ("https://www.instagram.com/username/?hl=ru#profile", ("username", "https://www.instagram.com/username/")),
    ],
)
def test_normalize_instagram_profile_url_accepts_profile_urls(value: str, expected: tuple[str, str]) -> None:
    assert normalize_instagram_profile_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://www.instagram.com/p/post_id/",
        "https://www.instagram.com/reel/reel_id/",
        "https://www.instagram.com/reels/",
        "https://www.instagram.com/stories/username/",
    ],
)
def test_normalize_instagram_profile_url_rejects_post_reel_and_stories_urls(value: str) -> None:
    assert normalize_instagram_profile_url(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "https://www.instagram.com/explore/",
        "https://www.instagram.com/accounts/login/",
        "https://www.instagram.com/direct/inbox/",
        "https://www.instagram.com/tv/",
        "https://www.instagram.com/developer/",
        "https://www.instagram.com/about/",
        "https://www.instagram.com/legal/",
        "https://www.instagram.com/privacy/",
        "https://www.instagram.com/terms/",
        "https://www.instagram.com/web/",
        "https://www.instagram.com/",
    ],
)
def test_normalize_instagram_profile_url_rejects_service_urls(value: str) -> None:
    assert normalize_instagram_profile_url(value) is None


def test_normalize_instagram_profile_url_rejects_extra_path_after_username() -> None:
    assert normalize_instagram_profile_url("https://www.instagram.com/username/p/post_id/") is None


@pytest.mark.parametrize(
    "value",
    [
        "https://www.instagram.com/user-name/",
        "https://www.instagram.com/user$name/",
        "https://www.instagram.com/очень/",
        "https://www.instagram.com/abcdefghijklmnopqrstuvwxyzabcde/",
    ],
)
def test_normalize_instagram_profile_url_rejects_invalid_username(value: str) -> None:
    assert normalize_instagram_profile_url(value) is None


def test_discovery_service_deduplicates_candidates_by_username() -> None:
    service = DiscoveryService(
        query_builder=_query_builder(["q1", "q2"]),
        search_client=_search_client(
            {
                "q1": [{"url": "https://www.instagram.com/Creator/", "title": "First"}],
                "q2": [{"url": "https://instagram.com/creator?hl=ru", "title": "Second"}],
            }
        ),
    )

    result = service.discover(IdealBloggerProfile(niche="бьюти"), reference_usernames=set())

    assert result.total_candidates == 1
    assert result.candidates[0].username == "creator"
    assert result.candidates[0].title == "First"


def test_discovery_service_excludes_reference_bloggers() -> None:
    service = DiscoveryService(
        query_builder=_query_builder(["q1"]),
        search_client=_search_client(
            {
                "q1": [
                    {"url": "https://www.instagram.com/reference/"},
                    {"url": "https://www.instagram.com/new_creator/"},
                ]
            }
        ),
    )

    result = service.discover(IdealBloggerProfile(niche="бьюти"), reference_usernames={"reference"})

    assert [candidate.username for candidate in result.candidates] == ["new_creator"]


def test_discovery_service_continues_when_one_query_fails() -> None:
    service = DiscoveryService(
        query_builder=_query_builder(["bad", "good"]),
        search_client=_search_client(
            {
                "bad": BraveSearchClientError("timeout"),
                "good": [{"url": "https://www.instagram.com/good_creator/"}],
            }
        ),
    )

    result = service.discover(IdealBloggerProfile(niche="бьюти"), reference_usernames=set())

    assert result.total_candidates == 1
    assert result.candidates[0].username == "good_creator"


def test_discovery_service_raises_clear_error_when_all_queries_fail() -> None:
    service = DiscoveryService(
        query_builder=_query_builder(["bad", "worse"]),
        search_client=_search_client(
            {
                "bad": BraveSearchClientError("timeout"),
                "worse": BraveSearchClientError("network"),
            }
        ),
    )

    with pytest.raises(DiscoveryServiceError, match="Первая ошибка: timeout"):
        service.discover(IdealBloggerProfile(niche="бьюти"), reference_usernames=set())


def test_discovery_service_logs_safe_query_failure_reason(caplog: pytest.LogCaptureFixture) -> None:
    service = DiscoveryService(
        query_builder=_query_builder(["bad", "good"]),
        search_client=_search_client(
            {
                "bad": BraveSearchClientError("Brave Search отклонил авторизацию (HTTP 401)."),
                "good": [{"url": "https://www.instagram.com/good_creator/"}],
            }
        ),
    )

    service.discover(IdealBloggerProfile(niche="бьюти"), reference_usernames=set())

    assert "Brave Search отклонил авторизацию" in caplog.text
    assert "secret" not in caplog.text.lower()


def test_discovery_result_serializes_to_json_shape() -> None:
    service = DiscoveryService(
        query_builder=_query_builder(["q1"]),
        search_client=_search_client({"q1": [{"url": "https://www.instagram.com/creator/"}]}),
    )

    result = service.discover(IdealBloggerProfile(niche="бьюти"), reference_usernames=set())
    payload = result.model_dump(mode="json")

    assert isinstance(result, DiscoveryResult)
    assert payload == {
        "queries": ["q1"],
        "candidates": [
            {
                "username": "creator",
                "profile_url": "https://www.instagram.com/creator/",
                "source_query": "q1",
                "title": None,
                "description": None,
            }
        ],
        "total_candidates": 1,
    }


def test_reference_usernames_from_urls_extracts_normalized_usernames() -> None:
    assert reference_usernames_from_urls(
        [
            "https://www.instagram.com/Creator/",
            "https://www.instagram.com/p/post_id/",
            "https://instagram.com/second?hl=ru",
        ]
    ) == {"creator", "second"}


def _query_builder(queries: list[str]) -> Any:
    class FakeQueryBuilder:
        def build_queries(self, ideal_profile: IdealBloggerProfile) -> list[str]:
            return queries

    return FakeQueryBuilder()


def _search_client(results_by_query: dict[str, list[dict[str, Any]] | Exception]) -> Any:
    class FakeSearchClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def search(self, query: str) -> list[dict[str, Any]]:
            self.calls.append(query)
            result = results_by_query[query]
            if isinstance(result, Exception):
                raise result
            return result

    return FakeSearchClient()
