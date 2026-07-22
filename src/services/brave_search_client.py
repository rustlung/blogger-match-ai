from __future__ import annotations

from typing import Any

import httpx

from src.utils.logger import logger


BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchClientError(RuntimeError):
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

        if response.status_code >= 400:
            raise BraveSearchClientError(_http_error_message(response.status_code))

        try:
            data = response.json()
        except ValueError as exc:
            raise BraveSearchClientError("Brave Search returned invalid JSON.") from exc

        web_results = data.get("web")
        if web_results is None:
            logger.warning("Brave Search response has no web results block.")
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
