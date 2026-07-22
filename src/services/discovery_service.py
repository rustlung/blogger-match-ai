from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from src.models.discovery import DiscoveryCandidate, DiscoveryResult
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.brave_search_client import BraveSearchClient, BraveSearchClientError
from src.services.discovery_query_builder import DiscoveryQueryBuilder
from src.utils.logger import logger


_USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")
_RESERVED_PATHS = {
    "p",
    "reel",
    "reels",
    "stories",
    "explore",
    "accounts",
    "direct",
    "tv",
    "developer",
    "about",
    "legal",
    "privacy",
    "terms",
    "web",
}


class DiscoveryServiceError(RuntimeError):
    pass


class DiscoveryService:
    def __init__(
        self,
        query_builder: DiscoveryQueryBuilder,
        search_client: BraveSearchClient,
    ) -> None:
        self._query_builder = query_builder
        self._search_client = search_client

    def discover(
        self,
        ideal_profile: IdealBloggerProfile,
        reference_usernames: set[str],
    ) -> DiscoveryResult:
        queries = self._query_builder.build_queries(ideal_profile)
        if not queries:
            raise DiscoveryServiceError("Не удалось построить поисковые запросы для discovery.")

        candidates: list[DiscoveryCandidate] = []
        seen_usernames: set[str] = {username.casefold() for username in reference_usernames if username}
        successful_queries = 0
        failure_messages: list[str] = []

        for query_index, query in enumerate(queries, start=1):
            try:
                search_results = self._search_client.search(query)
            except BraveSearchClientError as exc:
                failure_messages.append(str(exc))
                logger.warning(
                    "Brave Search query failed: error_type=%s query_index=%s message=%s",
                    type(exc).__name__,
                    query_index,
                    str(exc),
                )
                continue

            successful_queries += 1
            for item in search_results:
                candidate = _candidate_from_search_item(item, query)
                if candidate is None:
                    continue

                username_key = candidate.username.casefold()
                if username_key in seen_usernames:
                    continue

                seen_usernames.add(username_key)
                candidates.append(candidate)

        if successful_queries == 0:
            first_failure = failure_messages[0] if failure_messages else "причина неизвестна"
            raise DiscoveryServiceError(
                "Не удалось выполнить ни один поисковый запрос Brave Search. "
                f"Первая ошибка: {first_failure}"
            )

        return DiscoveryResult(
            queries=queries,
            candidates=candidates,
            total_candidates=len(candidates),
        )


def normalize_instagram_profile_url(value: str | None) -> tuple[str, str] | None:
    if value is None:
        return None

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"}:
        return None

    hostname = (parsed.hostname or "").casefold()
    if hostname not in {"instagram.com", "www.instagram.com"}:
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) != 1:
        return None

    username = segments[0].casefold()
    if username in _RESERVED_PATHS:
        return None

    if not _USERNAME_RE.fullmatch(username):
        return None

    return username, f"https://www.instagram.com/{username}/"


def reference_usernames_from_urls(values: list[str]) -> set[str]:
    usernames: set[str] = set()
    for value in values:
        normalized = normalize_instagram_profile_url(value)
        if normalized is not None:
            usernames.add(normalized[0])
    return usernames


def _candidate_from_search_item(item: dict[str, Any], source_query: str) -> DiscoveryCandidate | None:
    normalized = normalize_instagram_profile_url(_text_or_none(item.get("url")))
    if normalized is None:
        return None

    username, profile_url = normalized
    return DiscoveryCandidate(
        username=username,
        profile_url=profile_url,
        source_query=source_query,
        title=_text_or_none(item.get("title")),
        description=_text_or_none(item.get("description")),
    )


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None
