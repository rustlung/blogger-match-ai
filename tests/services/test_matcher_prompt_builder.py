from src.models.blogger import BloggerProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.matcher_prompt_builder import MatcherPromptBuilder


def test_matcher_system_prompt_contains_geography_and_structured_output_rules() -> None:
    prompt = MatcherPromptBuilder().build_system_prompt().casefold()

    assert "целевой рынок: россия" in prompt
    assert "укра" in prompt
    assert "не считай русскоязычный профиль автоматически российским" in prompt
    assert "не выдумывай" in prompt
    assert "structured output" in prompt


def test_matcher_user_prompt_contains_ideal_profile_and_candidate_without_raw_data() -> None:
    prompt = MatcherPromptBuilder().build_user_prompt(
        ideal_profile=IdealBloggerProfile(
            niche="бьюти",
            min_followers=1000,
            required_topics=["уход"],
            preferred_regions=["Россия"],
        ),
        candidate_profile=BloggerProfile(
            profile_url="https://www.instagram.com/creator/",
            username="creator",
            biography="Бьюти и уход",
            followers_count=5000,
            raw_data={"secret_raw": "do-not-send"},
        ),
    )

    assert "IdealBloggerProfile" in prompt
    assert "Candidate BloggerProfile" in prompt
    assert "бьюти" in prompt
    assert "creator" in prompt
    assert "Бьюти и уход" in prompt
    assert "raw_data" not in prompt
    assert "secret_raw" not in prompt
