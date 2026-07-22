from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.blogger import BloggerProfile
from src.models.failed_profile import FailedProfile


def test_create_failed_profile() -> None:
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
        error_description="Post does not exist",
        retryable=False,
    )

    assert failed_profile.input_url == "https://www.instagram.com/missing/"
    assert failed_profile.username == "missing"
    assert failed_profile.error_code == "not_found"
    assert failed_profile.error_description == "Post does not exist"
    assert failed_profile.retryable is False


def test_create_apify_enrichment_result() -> None:
    profile = _blogger_profile()
    failed_profile = FailedProfile(
        input_url="https://www.instagram.com/missing/",
        username="missing",
        error_code="not_found",
    )

    result = ApifyEnrichmentResult(
        profiles=[profile],
        failed_profiles=[failed_profile],
    )

    assert result.profiles == [profile]
    assert result.failed_profiles == [failed_profile]


def test_apify_enrichment_result_lists_do_not_share_defaults() -> None:
    first_result = ApifyEnrichmentResult()
    second_result = ApifyEnrichmentResult()

    first_result.profiles.append(_blogger_profile())
    first_result.failed_profiles.append(
        FailedProfile(
            input_url="https://www.instagram.com/missing/",
            error_code="not_found",
        )
    )

    assert second_result.profiles == []
    assert second_result.failed_profiles == []
    assert first_result.profiles is not second_result.profiles
    assert first_result.failed_profiles is not second_result.failed_profiles


def _blogger_profile() -> BloggerProfile:
    return BloggerProfile(
        input_url="https://www.instagram.com/creator/",
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        raw_data={"username": "creator"},
    )
