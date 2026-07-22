from __future__ import annotations

from typing import Any

import pytest

from src.services import brave_search_client
from src.services.brave_search_client import BraveSearchClient, BraveSearchClientError, BraveSearchHttpError


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


def test_brave_search_client_logs_query_status_and_web_results_count_for_normal_response(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="blogger_match_ai")
    monkeypatch.setattr(
        brave_search_client,
        "httpx",
        _fake_httpx(
            response=_response(
                200,
                {
                    "web": {
                        "results": [
                            {"url": "https://instagram.com/a/"},
                            {"url": "https://instagram.com/b/"},
                        ]
                    }
                },
            )
        ),
    )

    result = BraveSearchClient(api_key="secret-key").search("site:instagram.com тест")

    assert len(result) == 2
    assert "query=site:instagram.com тест" in caplog.text
    assert "status=200" in caplog.text
    assert "web_results_count=2" in caplog.text


def test_brave_search_client_logs_zero_web_results_for_empty_results_list(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="blogger_match_ai")
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(200, {"web": {"results": []}})))

    result = BraveSearchClient(api_key="secret-key").search("query")

    assert result == []
    assert "status=200" in caplog.text
    assert "web_results_count=0" in caplog.text


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


def test_brave_search_client_http_error_uses_specialized_error_and_status_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(503, {"message": "down"})))

    with pytest.raises(BraveSearchHttpError, match="HTTP 503") as exc_info:
        BraveSearchClient(api_key="secret-key").search("query")

    assert "web results" not in str(exc_info.value)


def test_brave_search_client_http_error_does_not_expose_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(401, {"error": "auth"})))

    with pytest.raises(BraveSearchClientError) as exc_info:
        BraveSearchClient(api_key="secret-key").search("query")

    assert "secret-key" not in str(exc_info.value)


def test_brave_search_client_returns_empty_list_when_web_block_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="blogger_match_ai")
    monkeypatch.setattr(
        brave_search_client,
        "httpx",
        _fake_httpx(response=_response(200, {"query": "test", "mixed": {"main": []}})),
    )

    result = BraveSearchClient(api_key="secret-key").search("query")

    assert result == []
    assert "Brave Search response has no web results block." in caplog.text
    assert "top_level_keys=['mixed', 'query']" in caplog.text
    assert "has_error=False" in caplog.text
    assert "has_message=False" in caplog.text
    assert "web_results_count=0" in caplog.text


def test_brave_search_client_logs_error_message_fields_when_web_block_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="blogger_match_ai")
    payload = {
        "error": {"type": "usage"},
        "message": "No web results available",
        "code": "empty",
        "detail": "diagnostic",
    }
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(200, payload)))

    result = BraveSearchClient(api_key="secret-key").search("query")

    assert result == []
    assert "has_error=True" in caplog.text
    assert "has_message=True" in caplog.text
    assert "has_code=True" in caplog.text
    assert "has_detail=True" in caplog.text
    assert "No web results available" in caplog.text


def test_brave_search_client_logs_safe_response_fragment_without_secret(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="blogger_match_ai")
    payload = {"message": "x" * 1200}
    monkeypatch.setattr(brave_search_client, "httpx", _fake_httpx(response=_response(200, payload)))

    BraveSearchClient(api_key="secret-key").search("query")

    assert "response_fragment=" in caplog.text
    assert "secret-key" not in caplog.text
    assert "X-Subscription-Token" not in caplog.text


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
            self.text = str(payload)

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
