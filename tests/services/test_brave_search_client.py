from __future__ import annotations

from typing import Any

import pytest

from src.services import brave_search_client
from src.services.brave_search_client import BraveSearchClient, BraveSearchClientError


def test_brave_search_client_sends_expected_request_without_exposing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_httpx = _fake_httpx(response=_response(200, {"web": {"results": [{"url": "https://instagram.com/a/"}]}}))
    monkeypatch.setattr(brave_search_client, "httpx", fake_httpx)

    result = BraveSearchClient(api_key="secret-key", timeout_seconds=12).search("query")

    assert result == [{"url": "https://instagram.com/a/"}]
    request = fake_httpx.clients[0].requests[0]
    assert request["url"] == brave_search_client.BRAVE_SEARCH_ENDPOINT
    assert request["headers"]["Accept"] == "application/json"
    assert request["headers"]["Accept-Encoding"] == "gzip"
    assert request["headers"]["X-Subscription-Token"] == "secret-key"
    assert request["params"] == {
        "q": "query",
        "country": "RU",
        "search_lang": "ru",
        "count": 20,
    }


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_message"),
    [
        (401, {"error": "auth"}, "BRAVE_SEARCH_API_KEY"),
        (422, {"error": "params"}, "параметры запроса"),
        (429, {"error": "quota"}, "лимит тарифа"),
        (500, {"error": "server"}, "серверную ошибку"),
        (200, {"web": {"results": None}}, "web results"),
    ],
)
def test_brave_search_client_raises_error_for_bad_responses(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    payload: dict[str, Any],
    expected_message: str,
) -> None:
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(status_code, payload)))

    with pytest.raises(BraveSearchClientError, match=expected_message):
        BraveSearchClient(api_key="secret-key").search("query")


def test_brave_search_client_http_error_does_not_expose_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(401, {"error": "auth"})))

    with pytest.raises(BraveSearchClientError) as exc_info:
        BraveSearchClient(api_key="secret-key").search("query")

    assert "secret-key" not in str(exc_info.value)


def test_brave_search_client_returns_empty_list_when_web_block_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(200, {})))

    result = BraveSearchClient(api_key="secret-key").search("query")

    assert result == []


def test_brave_search_client_raises_error_for_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_invalid_json_response()))

    with pytest.raises(BraveSearchClientError, match="invalid JSON"):
        BraveSearchClient(api_key="secret-key").search("query")


@pytest.mark.parametrize(
    ("exception_attr", "expected_message"),
    [
        ("TimeoutException", "timed out"),
        ("RequestError", "network"),
    ],
)
def test_brave_search_client_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
    exception_attr: str,
    expected_message: str,
) -> None:
    exception_type = getattr(brave_search_client.httpx, exception_attr)
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(exception=exception_type("request failed")))

    with pytest.raises(BraveSearchClientError, match=expected_message) as exc_info:
        BraveSearchClient(api_key="secret-key").search("query")

    assert "secret-key" not in str(exc_info.value)


def test_brave_search_client_rejects_missing_api_key_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_httpx = _fake_httpx(response=_response(200, {"web": {"results": []}}))
    monkeypatch.setattr(brave_search_client, "httpx", fake_httpx)

    with pytest.raises(BraveSearchClientError, match="BRAVE_SEARCH_API_KEY"):
        BraveSearchClient(api_key="").search("query")

    assert fake_httpx.clients == []


def _response(status_code: int, payload: dict[str, Any]) -> Any:
    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code

        def json(self) -> dict[str, Any]:
            return payload

    return FakeResponse()


def _invalid_json_response() -> Any:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            raise ValueError("bad json")

    return FakeResponse()


def _fake_httpx(response: Any | None = None, exception: Exception | None = None) -> Any:
    clients: list[Any] = []

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout
            self.requests: list[dict[str, Any]] = []
            clients.append(self)

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, **kwargs: Any) -> Any:
            self.requests.append({"url": url, **kwargs})
            if exception is not None:
                raise exception
            return response

    return type(
        "FakeHttpx",
        (),
        {
            "Client": FakeClient,
            "TimeoutException": brave_search_client.httpx.TimeoutException,
            "RequestError": brave_search_client.httpx.RequestError,
            "clients": clients,
        },
    )
