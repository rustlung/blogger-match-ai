from __future__ import annotations

import re

from src.models.ideal_blogger_profile import IdealBloggerProfile


MAX_DISCOVERY_QUERIES = 5
MAX_TOPIC_LENGTH = 60
_TOPIC_SPLIT_RE = re.compile(r"[/,;:()]+")


class DiscoveryQueryBuilder:
    def build_queries(self, ideal_profile: IdealBloggerProfile) -> list[str]:
        topics = _unique_topics(
            [
                *ideal_profile.required_topics,
                ideal_profile.niche,
            ]
        )
        if not topics:
            return []

        queries = [f'site:instagram.com "{topic}" блогер Россия' for topic in topics[:MAX_DISCOVERY_QUERIES]]
        if len(queries) < MAX_DISCOVERY_QUERIES:
            queries.append(f'site:instagram.com "для сотрудничества" "{topics[0]}"')

        return queries[:MAX_DISCOVERY_QUERIES]


def _unique_topics(values: list[str | None]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value is None:
            continue

        for topic in _topic_candidates(str(value)):
            key = topic.casefold()
            if not topic or key in seen:
                continue

            seen.add(key)
            topics.append(topic)

    return topics


def _topic_candidates(value: str) -> list[str]:
    text = " ".join(value.strip().split())
    if not text:
        return []

    candidates: list[str] = []
    for part in _TOPIC_SPLIT_RE.split(text):
        topic = _clean_topic(part)
        if topic:
            candidates.append(topic)

    if not candidates:
        cleaned = _clean_topic(text)
        if cleaned:
            candidates.append(cleaned)

    return candidates


def _clean_topic(value: str) -> str:
    topic = value.strip(" .\"'«»")
    if len(topic) > MAX_TOPIC_LENGTH:
        topic = topic[:MAX_TOPIC_LENGTH].rsplit(" ", 1)[0].strip()
    return topic
