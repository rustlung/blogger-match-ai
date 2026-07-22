from src.models.blogger import BloggerProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.prompt_builder import PromptBuilder


def test_build_system_prompt_returns_non_empty_string() -> None:
    prompt = PromptBuilder().build_system_prompt()

    assert isinstance(prompt, str)
    assert prompt
    assert "influencer-маркетингу" in prompt


def test_build_system_prompt_requires_russian_analytical_output() -> None:
    prompt = PromptBuilder().build_system_prompt()

    assert "исключительно на русском языке" in prompt
    assert "strengths, weaknesses, recommendation и explanation" in prompt
    assert "естественным деловым русским языком" in prompt
    assert "Не добавляй английский дубль или перевод" in prompt


def test_build_user_prompt_contains_relevant_profile_data() -> None:
    prompt = PromptBuilder().build_user_prompt(
        ideal_profile=IdealBloggerProfile(
            niche="beauty",
            min_followers=1000,
            max_followers=50000,
            required_topics=["skincare"],
        ),
        blogger=_blogger_profile(),
    )

    assert "beauty" in prompt
    assert "creator" in prompt
    assert "Helpful beauty bio" in prompt
    assert "12345" in prompt
    assert "Morning skincare routine" in prompt
    assert "No caption" in prompt
    assert "skincare" in prompt


def test_build_user_prompt_does_not_include_raw_data_or_blocked_post_fields() -> None:
    prompt = PromptBuilder().build_user_prompt(
        ideal_profile=IdealBloggerProfile(niche="beauty"),
        blogger=_blogger_profile(),
    )

    assert "raw_data" not in prompt
    assert "imageUrl" not in prompt
    assert "https://images.example/post.jpg" not in prompt
    assert "profilePicUrl" not in prompt
    assert "https://images.example/profile.jpg" not in prompt
    assert "childPosts" not in prompt


def test_build_user_prompt_handles_empty_values() -> None:
    blogger = BloggerProfile(
        input_url=None,
        profile_url="https://www.instagram.com/empty/",
        username="empty",
        full_name=None,
        biography=None,
        followers_count=None,
        follows_count=None,
        posts_count=None,
        verified=None,
        private=None,
        business_account=None,
        business_category_name=None,
        external_url=None,
        public_email=None,
        public_phone_number=None,
        profile_pic_url=None,
        raw_data={"latestPosts": [{"caption": "", "hashtags": []}]},
    )

    prompt = PromptBuilder().build_user_prompt(
        ideal_profile=IdealBloggerProfile(niche="fitness"),
        blogger=blogger,
    )

    assert "None" not in prompt
    assert "Not specified" in prompt
    assert "No caption" in prompt


def _blogger_profile() -> BloggerProfile:
    return BloggerProfile(
        input_url="https://www.instagram.com/creator/",
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        full_name="Creator Name",
        biography="Helpful beauty bio",
        followers_count=12345,
        follows_count=500,
        posts_count=100,
        verified=False,
        private=False,
        business_account=True,
        business_category_name="Beauty",
        external_url="https://creator.example",
        public_email="creator@example.com",
        public_phone_number=None,
        profile_pic_url="https://images.example/profile.jpg",
        raw_data={
            "profilePicUrl": "https://images.example/profile.jpg",
            "latestPosts": [
                {
                    "caption": "Morning skincare routine",
                    "hashtags": ["skincare", "beauty"],
                    "imageUrl": "https://images.example/post.jpg",
                    "childPosts": [{"caption": "Hidden child caption"}],
                },
                {
                    "caption": "",
                    "hashtags": [],
                },
            ],
        },
    )
