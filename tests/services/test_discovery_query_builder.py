from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.discovery_query_builder import MAX_DISCOVERY_QUERIES, MAX_TOPIC_LENGTH, DiscoveryQueryBuilder


def test_query_builder_builds_no_more_than_five_queries() -> None:
    profile = IdealBloggerProfile(
        niche="лайфстайл",
        required_topics=["бьюти", "мода", "уход", "спорт", "еда", "путешествия"],
    )

    queries = DiscoveryQueryBuilder().build_queries(profile)

    assert len(queries) <= MAX_DISCOVERY_QUERIES


def test_query_builder_uses_ideal_profile_topics() -> None:
    profile = IdealBloggerProfile(
        niche="лайфстайл",
        required_topics=["находки wildberries"],
    )

    queries = DiscoveryQueryBuilder().build_queries(profile)

    assert 'site:instagram.com "находки wildberries" блогер Россия' in queries
    assert 'site:instagram.com "лайфстайл" блогер Россия' in queries


def test_query_builder_removes_empty_values_and_case_insensitive_duplicates() -> None:
    profile = IdealBloggerProfile(
        niche="Бьюти",
        required_topics=["", "  ", "бьюти", "БЬЮТИ", "уход"],
    )

    queries = DiscoveryQueryBuilder().build_queries(profile)

    assert queries.count('site:instagram.com "бьюти" блогер Россия') == 1
    assert not any('""' in query for query in queries)
    assert 'site:instagram.com "уход" блогер Россия' in queries


def test_query_builder_adds_deterministic_commercial_query_when_possible() -> None:
    profile = IdealBloggerProfile(niche="бьюти")

    queries = DiscoveryQueryBuilder().build_queries(profile)

    assert 'site:instagram.com "для сотрудничества" "бьюти"' in queries


def test_query_builder_splits_complex_llm_topics_into_short_search_phrases() -> None:
    profile = IdealBloggerProfile(
        niche="лайфстайл и бьюти с фокусом на находки и визуально-эстетичный контент",
        required_topics=[
            "лайфстайл (повседневный стиль, дом, личные находки)",
            "бьюти / уход / косметика / полезные находки",
        ],
    )

    queries = DiscoveryQueryBuilder().build_queries(profile)

    assert 'site:instagram.com "лайфстайл" блогер Россия' in queries
    assert 'site:instagram.com "повседневный стиль" блогер Россия' in queries
    assert 'site:instagram.com "бьюти" блогер Россия' in queries
    assert all(len(_quoted_topic(query)) <= MAX_TOPIC_LENGTH for query in queries if "блогер Россия" in query)


def _quoted_topic(query: str) -> str:
    return query.split('"')[1]
