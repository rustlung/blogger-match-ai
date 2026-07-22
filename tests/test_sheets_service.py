import pytest

from src.services.sheets_service import (
    extract_instagram_urls_from_column,
    normalize_instagram_profile_url,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("@username", "https://www.instagram.com/username/"),
        ("username", "https://www.instagram.com/username/"),
        ("user.name_123", "https://www.instagram.com/user.name_123/"),
        ("https://instagram.com/username", "https://www.instagram.com/username/"),
        ("https://www.instagram.com/username", "https://www.instagram.com/username/"),
        ("instagram.com/username", "https://www.instagram.com/username/"),
        ("https://instagram.com/username/", "https://www.instagram.com/username/"),
        ("https://instagram.com/username/?utm_source=test", "https://www.instagram.com/username/"),
        ("https://instagram.com/username/#profile", "https://www.instagram.com/username/"),
        ("https://WWW.INSTAGRAM.COM/username", "https://www.instagram.com/username/"),
    ],
)
def test_normalize_instagram_profile_url_valid(value: str, expected: str) -> None:
    assert normalize_instagram_profile_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "@",
        "https://example.com/username",
        "https://instagram.com/p/post_id",
        "https://instagram.com/reel/reel_id",
        "https://instagram.com/reels/",
        "https://instagram.com/stories/username",
        "https://instagram.com/explore/",
        "https://instagram.com/accounts/login",
        "https://instagram.com/direct/inbox",
        "user name",
        "user-name",
        "user$name",
    ],
)
def test_normalize_instagram_profile_url_invalid(value: str) -> None:
    assert normalize_instagram_profile_url(value) is None


def test_extract_instagram_urls_from_column_sequential_rows() -> None:
    values = [
        ["https://instagram.com/blogger1"],
        ["https://instagram.com/blogger2"],
    ]

    assert extract_instagram_urls_from_column(values) == [
        "https://www.instagram.com/blogger1/",
        "https://www.instagram.com/blogger2/",
    ]


def test_extract_instagram_urls_from_column_skips_empty_physical_rows() -> None:
    values = [
        ["https://instagram.com/blogger1"],
        [],
        ["https://instagram.com/blogger2"],
        [],
        [],
        [],
        ["@blogger3"],
    ]

    assert extract_instagram_urls_from_column(values) == [
        "https://www.instagram.com/blogger1/",
        "https://www.instagram.com/blogger2/",
        "https://www.instagram.com/blogger3/",
    ]


def test_extract_instagram_urls_from_column_skips_empty_strings_and_invalid_values() -> None:
    values = [
        [""],
        ["https://example.com/blogger"],
        ["https://instagram.com/p/post_id"],
        ["valid_blogger"],
    ]

    assert extract_instagram_urls_from_column(values) == [
        "https://www.instagram.com/valid_blogger/",
    ]


def test_extract_instagram_urls_from_column_removes_duplicates_preserving_order() -> None:
    values = [
        ["@first"],
        ["https://instagram.com/second"],
        ["instagram.com/first"],
        ["@third"],
        ["https://www.instagram.com/second/?utm=test"],
    ]

    assert extract_instagram_urls_from_column(values) == [
        "https://www.instagram.com/first/",
        "https://www.instagram.com/second/",
        "https://www.instagram.com/third/",
    ]


def test_extract_instagram_urls_from_column_mixed_usernames_and_urls() -> None:
    values = [
        ["@blogger_one"],
        ["blogger.two"],
        ["https://www.instagram.com/blogger3/"],
    ]

    assert extract_instagram_urls_from_column(values) == [
        "https://www.instagram.com/blogger_one/",
        "https://www.instagram.com/blogger.two/",
        "https://www.instagram.com/blogger3/",
    ]


def test_extract_instagram_urls_from_column_empty_column() -> None:
    assert extract_instagram_urls_from_column([[], [""], []]) == []
