from __future__ import annotations

from typing import Any

from src.models.blogger import BloggerProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile


class PromptBuilder:
    def build_system_prompt(self) -> str:
        return """
Ты эксперт по influencer-маркетингу.
Ты анализируешь Instagram-блогеров и оцениваешь, насколько они соответствуют требованиям бренда.
Сравнивай кандидата только с предоставленным идеальным профилем и данными кандидата.
Оценивай соответствие нише, аудитории, качество контента, brand safety и общую пригодность.
Используй только информацию, предоставленную в prompt.
Не выдумывай факты, метрики, сведения об аудитории, регионы, языки или контакты.
Если данных недостаточно или они неоднозначны, снижай confidence.
Итоговая оценка должна быть объективной, сбалансированной и полезной для маркетолога.
Все аналитические текстовые значения structured output должны быть написаны исключительно на русском языке.
Поля strengths, weaknesses, recommendation и explanation должны быть заполнены естественным деловым русским языком.
Не добавляй английский дубль или перевод.
Не смешивай русский и английский язык, кроме usernames, URL, названий брендов, технических терминов и исходных данных профиля.
""".strip()

    def build_user_prompt(
        self,
        ideal_profile: IdealBloggerProfile,
        blogger: BloggerProfile,
    ) -> str:
        lines: list[str] = []

        lines.append("Ideal Blogger Profile")
        lines.append("")
        lines.append("Niche:")
        lines.append(_display(ideal_profile.niche))
        lines.append("")
        lines.append("Target gender:")
        lines.append(_display(ideal_profile.target_gender))
        lines.append("")
        lines.append("Target age range:")
        lines.append(_display(ideal_profile.target_age_range))
        lines.append("")
        lines.append("Followers:")
        lines.append(_followers_range(ideal_profile.min_followers, ideal_profile.max_followers))
        lines.append("")
        lines.append("Required topics:")
        lines.extend(_list_lines(ideal_profile.required_topics))
        lines.append("")
        lines.append("Excluded topics:")
        lines.extend(_list_lines(ideal_profile.excluded_topics))
        lines.append("")
        lines.append("Preferred regions:")
        lines.extend(_list_lines(ideal_profile.preferred_regions))
        lines.append("")
        lines.append("Preferred languages:")
        lines.extend(_list_lines(ideal_profile.preferred_languages))
        lines.append("")
        lines.append("Required brand style:")
        lines.append(_display(ideal_profile.required_brand_style))
        lines.append("")
        lines.append("---------------------")
        lines.append("")
        lines.append("Candidate")
        lines.append("")
        lines.append("Username:")
        lines.append(_display(blogger.username))
        lines.append("")
        lines.append("Profile URL:")
        lines.append(_display(blogger.profile_url))
        lines.append("")
        lines.append("Full name:")
        lines.append(_display(blogger.full_name))
        lines.append("")
        lines.append("Bio:")
        lines.append(_display(blogger.biography))
        lines.append("")
        lines.append("Followers:")
        lines.append(_display(blogger.followers_count))
        lines.append("")
        lines.append("Following:")
        lines.append(_display(blogger.follows_count))
        lines.append("")
        lines.append("Posts count:")
        lines.append(_display(blogger.posts_count))
        lines.append("")
        lines.append("Verified:")
        lines.append(_display(blogger.verified))
        lines.append("")
        lines.append("Private:")
        lines.append(_display(blogger.private))
        lines.append("")
        lines.append("Business account:")
        lines.append(_display(blogger.business_account))
        lines.append("")
        lines.append("Business category:")
        lines.append(_display(blogger.business_category_name))
        lines.append("")
        lines.append("External URL:")
        lines.append(_display(blogger.external_url))
        lines.append("")
        lines.append("Public email:")
        lines.append(_display(blogger.public_email))
        lines.append("")
        lines.append("Latest posts:")
        lines.extend(_latest_posts_lines(blogger.raw_data))

        return "\n".join(str(line) for line in lines)


def _display(value: object) -> str:
    if value is None or value == "":
        return "Not specified"
    return str(value)


def _followers_range(min_followers: int | None, max_followers: int | None) -> str:
    if min_followers is None and max_followers is None:
        return "Not specified"
    if min_followers is not None and max_followers is not None:
        return f"{min_followers} - {max_followers}"
    if min_followers is not None:
        return f"From {min_followers}"
    return f"Up to {max_followers}"


def _list_lines(values: list[str]) -> list[str]:
    if not values:
        return ["Not specified"]
    return [f"- {value}" for value in values if value]


def _latest_posts_lines(raw_data: dict[str, Any]) -> list[str]:
    posts = _extract_posts(raw_data)
    if not posts:
        return ["Not specified"]

    lines: list[str] = []
    for index, post in enumerate(posts, start=1):
        if not isinstance(post, dict):
            continue

        caption = _post_caption(post)
        hashtags = _post_hashtags(post)

        lines.append("")
        lines.append(f"{index}.")
        lines.append("Caption:")
        lines.append(caption or "No caption")
        lines.append("Hashtags:")
        lines.extend(_list_lines(hashtags))

    return lines or ["Not specified"]


def _extract_posts(raw_data: dict[str, Any]) -> list[Any]:
    for key in ("latestPosts", "latest_posts", "recentPosts", "recent_posts"):
        value = raw_data.get(key)
        if isinstance(value, list):
            return value
    return []


def _post_caption(post: dict[str, Any]) -> str:
    for key in ("caption", "text"):
        value = post.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _post_hashtags(post: dict[str, Any]) -> list[str]:
    value = post.get("hashtags")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
