from __future__ import annotations

import pytest

from src.models.blogger import BloggerProfile
from src.services.ideal_profile_prompt_builder import (
    MAX_CAPTIONS_PER_PROFILE,
    MAX_TEXT_LENGTH,
    IdealProfilePromptBuilder,
)


def test_build_user_prompt_rejects_empty_profile_list() -> None:
    builder = IdealProfilePromptBuilder()

    with pytest.raises(ValueError, match="empty"):
        builder.build_user_prompt([])


def test_build_user_prompt_includes_multiple_profiles_and_preserves_usernames() -> None:
    builder = IdealProfilePromptBuilder()

    prompt = builder.build_user_prompt([_blogger("krrazalia"), _blogger("brand_creator")])

    assert "Profiles count: 2" in prompt
    assert "krrazalia" in prompt
    assert "brand_creator" in prompt
    assert "Biography:" in prompt
    assert "Followers:" in prompt


def test_build_user_prompt_excludes_raw_data_and_image_fields() -> None:
    builder = IdealProfilePromptBuilder()

    prompt = builder.build_user_prompt([_blogger("creator")])

    assert "raw_data" not in prompt
    assert "profile_pic_url" not in prompt
    assert "profilePicUrl" not in prompt
    assert "imageUrl" not in prompt
    assert "videoUrl" not in prompt
    assert "thumbnailUrl" not in prompt
    assert "childPosts" not in prompt
    assert "https://images.example/avatar.jpg" not in prompt


def test_build_user_prompt_limits_captions_and_trims_long_text_without_mutating_model() -> None:
    builder = IdealProfilePromptBuilder()
    long_bio = "Б" * (MAX_TEXT_LENGTH + 50)
    long_caption = "К" * (MAX_TEXT_LENGTH + 50)
    blogger = _blogger(
        "creator",
        biography=long_bio,
        posts=[
            {"caption": f"{long_caption}-{index}", "hashtags": ["beauty"]}
            for index in range(MAX_CAPTIONS_PER_PROFILE + 3)
        ],
    )

    prompt = builder.build_user_prompt([blogger])

    assert blogger.biography == long_bio
    assert blogger.raw_data["latestPosts"][0]["caption"] == f"{long_caption}-0"
    assert prompt.count("Caption:") == MAX_CAPTIONS_PER_PROFILE
    assert long_bio not in prompt
    assert long_caption not in prompt
    assert "..." in prompt


def test_build_user_prompt_represents_missing_values_predictably() -> None:
    builder = IdealProfilePromptBuilder()
    blogger = _blogger("creator", biography=None, posts=[])

    prompt = builder.build_user_prompt([blogger])

    assert "Не указано" in prompt
    assert "Has external URL:\nНет" in prompt


def test_build_system_prompt_contains_ideal_profile_rules() -> None:
    builder = IdealProfilePromptBuilder()

    prompt = builder.build_system_prompt().lower()

    assert "русском языке" in prompt or "русский язык" in prompt
    assert "не выдумывай отсутствующие метрики" in prompt
    assert "анализируй выборку целиком" in prompt
    assert "повторяющиеся закономерности" in prompt
    assert "единичных особенностей" in prompt
    assert "structured output" in prompt


def _blogger(
    username: str,
    biography: str | None = "Лайфстайл, бьюти и сотрудничество с брендами.",
    posts: list[dict[str, object]] | None = None,
) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        full_name="Creator Name",
        biography=biography,
        followers_count=5000,
        follows_count=200,
        posts_count=40,
        verified=False,
        private=False,
        business_account=True,
        business_category_name="Digital creator",
        external_url=None,
        public_email=None,
        public_phone_number=None,
        profile_pic_url="https://images.example/avatar.jpg",
        raw_data={
            "username": username,
            "profilePicUrl": "https://images.example/avatar.jpg",
            "latestPosts": posts
            if posts is not None
            else [
                {
                    "caption": "Новый уход и повседневный образ",
                    "hashtags": ["beauty", "lifestyle"],
                    "imageUrl": "https://images.example/post.jpg",
                    "videoUrl": "https://video.example/post.mp4",
                    "thumbnailUrl": "https://images.example/thumb.jpg",
                    "childPosts": [{"caption": "nested"}],
                }
            ],
        },
    )
