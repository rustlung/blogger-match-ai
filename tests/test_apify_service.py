from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.services import apify_service
from src.services.apify_service import ApifyService, ApifyServiceError, parse_apify_profile


def test_parse_apify_profile_full_item() -> None:
    item = {
        "inputUrl": "https://www.instagram.com/source/",
        "url": "https://instagram.com/example/",
        "username": "example",
        "fullName": "Example User",
        "biography": "Bio",
        "followersCount": 123,
        "followsCount": 45,
        "postsCount": 6,
        "verified": True,
        "private": False,
        "isBusinessAccount": True,
        "businessCategoryName": "Creator",
        "externalUrl": "https://example.com",
        "publicEmail": "hello@example.com",
        "publicPhoneNumber": "+100000000",
        "profilePicUrl": "https://image.example/pic.jpg",
    }

    profile = parse_apify_profile(item)

    assert profile is not None
    assert profile.input_url == "https://www.instagram.com/source/"
    assert profile.profile_url == "https://www.instagram.com/example/"
    assert profile.username == "example"
    assert profile.full_name == "Example User"
    assert profile.biography == "Bio"
    assert profile.followers_count == 123
    assert profile.follows_count == 45
    assert profile.posts_count == 6
    assert profile.verified is True
    assert profile.private is False
    assert profile.business_account is True
    assert profile.business_category_name == "Creator"
    assert profile.external_url == "https://example.com"
    assert profile.public_email == "hello@example.com"
    assert profile.public_phone_number == "+100000000"
    assert profile.profile_pic_url == "https://image.example/pic.jpg"


def test_parse_apify_profile_alternative_field_names() -> None:
    item = {
        "inputUrl": "https://instagram.com/alt/",
        "ownerUsername": "alt",
        "profileUrl": "https://instagram.com/alt/",
        "name": "Alt Name",
        "bio": "Alt bio",
        "followers": 10,
        "followingCount": 20,
        "posts": 30,
        "isVerified": False,
        "isPrivate": True,
        "businessAccount": False,
        "categoryName": "Personal",
        "externalURL": "https://alt.example",
        "businessEmail": "alt@example.com",
        "businessPhoneNumber": "123",
        "profilePicUrlHD": "https://image.example/hd.jpg",
    }

    profile = parse_apify_profile(item)

    assert profile is not None
    assert profile.username == "alt"
    assert profile.full_name == "Alt Name"
    assert profile.biography == "Alt bio"
    assert profile.followers_count == 10
    assert profile.follows_count == 20
    assert profile.posts_count == 30
    assert profile.verified is False
    assert profile.private is True
    assert profile.business_account is False
    assert profile.business_category_name == "Personal"
    assert profile.external_url == "https://alt.example"
    assert profile.public_email == "alt@example.com"
    assert profile.public_phone_number == "123"
    assert profile.profile_pic_url == "https://image.example/hd.jpg"


def test_parse_apify_profile_numeric_strings() -> None:
    profile = parse_apify_profile(
        {
            "username": "numbers",
            "followersCount": "1000",
            "followsCount": "200",
            "postsCount": "30",
        }
    )

    assert profile is not None
    assert profile.followers_count == 1000
    assert profile.follows_count == 200
    assert profile.posts_count == 30


def test_parse_apify_profile_empty_values_become_none() -> None:
    profile = parse_apify_profile(
        {
            "username": "empty",
            "fullName": "",
            "followersCount": "",
            "followsCount": "not-a-number",
        }
    )

    assert profile is not None
    assert profile.full_name is None
    assert profile.followers_count is None
    assert profile.follows_count is None


def test_parse_apify_profile_username_from_profile_url() -> None:
    profile = parse_apify_profile({"profileUrl": "https://instagram.com/from_url/?utm=test"})

    assert profile is not None
    assert profile.username == "from_url"
    assert profile.profile_url == "https://www.instagram.com/from_url/"


def test_parse_apify_profile_normalizes_profile_url() -> None:
    profile = parse_apify_profile({"username": "normalize", "url": "instagram.com/normalize"})

    assert profile is not None
    assert profile.profile_url == "https://www.instagram.com/normalize/"


def test_parse_apify_profile_missing_optional_fields() -> None:
    profile = parse_apify_profile({"username": "minimal"})

    assert profile is not None
    assert profile.profile_url == "https://www.instagram.com/minimal/"
    assert profile.full_name is None
    assert profile.public_email is None


def test_parse_apify_profile_without_username_and_url_returns_none() -> None:
    assert parse_apify_profile({"fullName": "No identity"}) is None


def test_parse_apify_profile_raw_data_is_copied() -> None:
    item = {"username": "raw", "followersCount": 1}

    profile = parse_apify_profile(item)

    assert profile is not None
    assert profile.raw_data == item
    assert profile.raw_data is not item


def test_parse_apify_profile_bool_is_not_count() -> None:
    profile = parse_apify_profile({"username": "bool_count", "followersCount": True})

    assert profile is not None
    assert profile.followers_count is None


def test_apify_service_sends_one_batch_and_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, url: str, params: dict[str, str], json: dict[str, Any]) -> httpx.Response:
            captured["url"] = url
            captured["params"] = params
            captured["json"] = json
            return _json_response([{"username": "one"}])

    monkeypatch.setattr(httpx, "Client", FakeClient)

    result = ApifyService("secret", "apify~instagram-scraper", 123).enrich_profiles(
        [
            "https://www.instagram.com/one/",
            "https://www.instagram.com/one/",
            "",
            "https://www.instagram.com/two/",
        ]
    )

    assert len(result.profiles) == 1
    assert result.failed_profiles == []
    assert captured["timeout"] == 123
    assert captured["url"] == (
        "https://api.apify.com/v2/actors/apify~instagram-scraper/run-sync-get-dataset-items"
    )
    assert captured["params"] == {"token": "secret", "clean": "true", "format": "json"}
    assert captured["json"] == {
        "directUrls": [
            "https://www.instagram.com/one/",
            "https://www.instagram.com/two/",
        ],
        "resultsType": "details",
        "resultsLimit": 1,
    }


def test_apify_service_converts_actor_id_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, url: str, params: dict[str, str], json: dict[str, Any]) -> httpx.Response:
            captured["url"] = url
            return _json_response([{"username": "one"}])

    monkeypatch.setattr(httpx, "Client", FakeClient)

    ApifyService("secret", "apify/instagram-scraper", 300).enrich_profiles(["https://www.instagram.com/one/"])

    assert "apify~instagram-scraper" in captured["url"]


def test_apify_service_empty_list_raises_error() -> None:
    with pytest.raises(ApifyServiceError):
        ApifyService("secret", "actor", 300).enrich_profiles([])


def test_apify_service_empty_token_raises_error() -> None:
    with pytest.raises(ApifyServiceError):
        ApifyService("", "actor", 300).enrich_profiles(["https://www.instagram.com/one/"])


def test_apify_service_successful_list_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _json_response([{"username": "one"}, {"username": "two"}]))

    result = ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/one/"])

    assert isinstance(result, ApifyEnrichmentResult)
    assert [profile.username for profile in result.profiles] == ["one", "two"]
    assert result.failed_profiles == []


def test_apify_service_creates_failed_profiles_for_invalid_dataset_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _json_response([{"username": "valid"}, {"fullName": "invalid"}, "bad"]))

    result = ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/valid/"])

    assert [profile.username for profile in result.profiles] == ["valid"]
    assert [failed_profile.error_code for failed_profile in result.failed_profiles] == [
        "parse_error",
        "parse_error",
    ]


def test_apify_service_mixed_response_has_profiles_and_failed_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parse_calls: list[dict[str, Any]] = []
    original_parse = apify_service.parse_apify_profile

    def spy_parse(item: dict[str, Any]):
        parse_calls.append(item)
        return original_parse(item)

    monkeypatch.setattr(apify_service, "parse_apify_profile", spy_parse)
    _patch_client(
        monkeypatch,
        _json_response(
            [
                {"username": "valid"},
                {
                    "url": "https://www.instagram.com/missing/",
                    "username": "missing",
                    "error": "not_found",
                    "errorDescription": "Post does not exist",
                },
            ]
        ),
    )

    result = ApifyService("secret", "actor", 300).enrich_profiles(
        [
            "https://www.instagram.com/valid/",
            "https://www.instagram.com/missing/",
        ]
    )

    assert [profile.username for profile in result.profiles] == ["valid"]
    assert len(result.failed_profiles) == 1
    assert result.failed_profiles[0].input_url == "https://www.instagram.com/missing/"
    assert result.failed_profiles[0].username == "missing"
    assert result.failed_profiles[0].error_code == "not_found"
    assert result.failed_profiles[0].error_description == "Post does not exist"
    assert result.failed_profiles[0].retryable is False
    assert parse_calls == [{"username": "valid"}]


def test_apify_service_retryable_profile_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _json_response(
            [
                {
                    "url": "https://www.instagram.com/temporary/",
                    "username": "temporary",
                    "error": "temporarily_unavailable",
                }
            ]
        ),
    )

    result = ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/temporary/"])

    assert result.profiles == []
    assert result.failed_profiles[0].retryable is True


def test_apify_service_unknown_profile_error_is_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        _json_response(
            [
                {
                    "url": "https://www.instagram.com/unknown/",
                    "username": "unknown",
                    "error": "unexpected_error",
                }
            ]
        ),
    )

    result = ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/unknown/"])

    assert result.profiles == []
    assert result.failed_profiles[0].retryable is False


def test_apify_service_parse_error_does_not_break_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_parse(item: dict[str, Any]):
        if item.get("username") == "broken":
            raise ValueError("broken item")
        return parse_apify_profile(item)

    monkeypatch.setattr(apify_service, "parse_apify_profile", fake_parse)
    _patch_client(monkeypatch, _json_response([{"username": "valid"}, {"username": "broken"}]))

    result = ApifyService("secret", "actor", 300).enrich_profiles(
        [
            "https://www.instagram.com/valid/",
            "https://www.instagram.com/broken/",
        ]
    )

    assert [profile.username for profile in result.profiles] == ["valid"]
    assert len(result.failed_profiles) == 1
    assert result.failed_profiles[0].input_url == "https://www.instagram.com/broken/"
    assert result.failed_profiles[0].username == "broken"
    assert result.failed_profiles[0].error_code == "parse_error"
    assert result.failed_profiles[0].retryable is False


def test_apify_service_non_list_response_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _json_response({"username": "one"}))

    with pytest.raises(ApifyServiceError):
        ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/one/"])


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (httpx.TimeoutException("timeout"), "timed out"),
        (httpx.ConnectError("connect"), "подключиться"),
    ],
)
def test_apify_service_request_errors(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected_message: str,
) -> None:
    _patch_client_exception(monkeypatch, exception)

    with pytest.raises(ApifyServiceError, match=expected_message):
        ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/one/"])


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "авторизацию"),
        (402, "балансе"),
        (429, "частоты"),
        (500, "серверную"),
    ],
)
def test_apify_service_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    message: str,
) -> None:
    _patch_client(monkeypatch, httpx.Response(status_code, text="limit"))

    with pytest.raises(ApifyServiceError, match=message):
        ApifyService("secret", "actor", 300).enrich_profiles(["https://www.instagram.com/one/"])


def _json_response(data: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(data).encode("utf-8"),
        headers={"content-type": "application/json"},
    )


def _patch_client(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, url: str, params: dict[str, str], json: dict[str, Any]) -> httpx.Response:
            return response

    monkeypatch.setattr(httpx, "Client", FakeClient)


def _patch_client_exception(monkeypatch: pytest.MonkeyPatch, exception: Exception) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, url: str, params: dict[str, str], json: dict[str, Any]) -> httpx.Response:
            raise exception

    monkeypatch.setattr(httpx, "Client", FakeClient)
