from __future__ import annotations

import json
from typing import Any

import httpx

from src.utils.logger import logger


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchClientError(RuntimeError):
    pass


class BraveSearchHttpError(BraveSearchClientError):
    pass


class BraveSearchClient:
    def __init__(self, api_key: str, timeout_seconds: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def search(self, query: str) -> list[dict[str, Any]]:
        self._validate()

        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.get(
                    BRAVE_SEARCH_ENDPOINT,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self._api_key,
                    },
                    params={
                        "q": query,
                        "country": "RU",
                        "search_lang": "ru",
                        "count": 20,
                    },
                )
        except httpx.TimeoutException as exc:
            raise BraveSearchClientError("Brave Search request timed out.") from exc
        except httpx.RequestError as exc:
            raise BraveSearchClientError("Brave Search network request failed.") from exc

        try:
            data = response.json()
        except ValueError as exc:
            _log_response_diagnostics(
                query=query,
                status_code=response.status_code,
                data=None,
                response_text=_response_text(response),
            )
            raise BraveSearchClientError("Brave Search returned invalid JSON.") from exc

        if not isinstance(data, dict):
            _log_response_diagnostics(
                query=query,
                status_code=response.status_code,
                data=None,
                response_text=str(data)[:1000],
            )
            raise BraveSearchClientError("Brave Search returned unexpected JSON shape.")

        _log_response_diagnostics(
            query=query,
            status_code=response.status_code,
            data=data,
            response_text=_safe_json_fragment(data),
        )

        if not 200 <= response.status_code < 300:
            raise BraveSearchHttpError(_http_error_message(response.status_code))

        web_results = data.get("web")
        if web_results is None:
            _log_missing_web_block(data)
            return []

        results = web_results.get("results")
        if not isinstance(results, list):
            raise BraveSearchClientError("Brave Search response does not contain web results.")

        logger.info("Brave Search query completed.")
        return [item for item in results if isinstance(item, dict)]

    def _validate(self) -> None:
        if not self._api_key:
            raise BraveSearchClientError("BRAVE_SEARCH_API_KEY is not configured.")

        if self._timeout_seconds <= 0:
            raise BraveSearchClientError("Brave Search timeout must be greater than 0.")


def _http_error_message(status_code: int) -> str:
    if status_code in {401, 403}:
        return f"Brave Search отклонил авторизацию (HTTP {status_code}). Проверьте BRAVE_SEARCH_API_KEY."

    if status_code == 422:
        return "Brave Search отклонил параметры запроса (HTTP 422)."

    if status_code == 429:
        return "Brave Search вернул ограничение частоты запросов или лимит тарифа (HTTP 429)."

    if status_code >= 500:
        return f"Brave Search временно недоступен или вернул серверную ошибку (HTTP {status_code})."

    return f"Brave Search returned HTTP {status_code}."


def _log_response_diagnostics(
    *,
    query: str,
    status_code: int,
    data: dict[str, Any] | None,
    response_text: str,
) -> None:
    logger.info(
        "Brave Search response diagnostics: query=%s status=%s web_results_count=%s",
        query,
        status_code,
        _web_results_count(data),
    )

    if data is not None and data.get("web") is None:
        _log_missing_web_details(data, response_text)


def _log_missing_web_block(data: dict[str, Any]) -> None:
    logger.warning("Brave Search response has no web results block.")


def _log_missing_web_details(data: dict[str, Any], response_text: str) -> None:
    logger.warning(
        "Brave Search missing web diagnostics: top_level_keys=%s has_error=%s has_message=%s has_code=%s has_detail=%s response_fragment=%s",
        sorted(str(key) for key in data.keys()),
        "error" in data,
        "message" in data,
        "code" in data,
        "detail" in data,
        response_text[:1000],
    )


def _web_results_count(data: dict[str, Any] | None) -> int | str:
    if data is None:
        return "unknown"

    web = data.get("web")
    if not isinstance(web, dict):
        return 0

    results = web.get("results")
    if isinstance(results, list):
        return len(results)

    return 0


def _response_text(response: Any) -> str:
    text = getattr(response, "text", "")
    if not isinstance(text, str):
        return ""
    return text[:1000]


def _safe_json_fragment(data: dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)[:1000]
    except (TypeError, ValueError):
        return str(data)[:1000]
