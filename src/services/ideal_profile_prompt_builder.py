from __future__ import annotations

from typing import Any

from src.models.blogger import BloggerProfile


MAX_CAPTIONS_PER_PROFILE = 5
MAX_TEXT_LENGTH = 500


class IdealProfilePromptBuilder:
    def build_system_prompt(self) -> str:
        return """
Ты эксперт по influencer-маркетингу.
Твоя задача — проанализировать выборку Instagram-блогеров, которые уже считаются подходящими, и построить общий портрет идеального блогера.
Анализируй выборку целиком, а не оценивай блогеров по отдельности.

Выделяй только повторяющиеся закономерности и отделяй их от:
- тематических кластеров;
- единичных особенностей;
- выбросов.

Не объединяй все тематики разных профилей в один обязательный список.
Поле ideal_profile.required_topics должно содержать только действительно общие или обязательные темы.
Темы отдельных кластеров указывай в observed_variations или explanation.
Новому блогеру не обязательно сочетать все обнаруженные тематики одновременно.

Учитывай тематики профилей, biography, количество подписчиков и публикаций, бизнес-категории, признаки готовности к сотрудничеству, captions, hashtags и brand safety по доступным текстовым данным.

Не выдумывай отсутствующие метрики: возраст, пол, географию и доход аудитории, engagement rate, охваты, рекламные показатели или Instagram Insights.
Не определяй preferred_regions только по языку контента.
Указывай регион лишь при наличии явных данных.

Если данных мало, они неполные или основаны только на одном профиле, явно укажи это в data_limitations и снижай confidence.

Поле confidence заполняй числом по шкале от 0 до 100.
0 означает полное отсутствие уверенности, 100 — максимально высокую уверенность.
Не используй шкалу от 0 до 1.

Все аналитические текстовые поля structured output должны быть написаны исключительно на русском языке.
Используй естественный деловой русский язык.
Usernames, URL, названия брендов и собственные имена не переводи без необходимости.
Не добавляй английский дубль или перевод.

Верни structured output, соответствующий модели IdealProfileAnalysis.
""".strip()

    def build_user_prompt(self, profiles: list[BloggerProfile]) -> str:
        if not profiles:
            raise ValueError("Reference profiles list is empty.")

        lines: list[str] = []
        lines.append("Reference Instagram Profiles")
        lines.append("")
        lines.append(f"Profiles count: {len(profiles)}")
        lines.append("")

        for index, profile in enumerate(profiles, start=1):
            lines.extend(_profile_lines(index, profile))

        return "\n".join(lines)


def _profile_lines(index: int, profile: BloggerProfile) -> list[str]:
    lines: list[str] = []
    lines.append("---------------------")
    lines.append(f"Profile {index}")
    lines.append("")
    lines.append("Username:")
    lines.append(_display(profile.username))
    lines.append("")
    lines.append("Full name:")
    lines.append(_display(_trim_text(profile.full_name)))
    lines.append("")
    lines.append("Biography:")
    lines.append(_display(_trim_text(profile.biography)))
    lines.append("")
    lines.append("Followers:")
    lines.append(_display(profile.followers_count))
    lines.append("")
    lines.append("Following:")
    lines.append(_display(profile.follows_count))
    lines.append("")
    lines.append("Posts count:")
    lines.append(_display(profile.posts_count))
    lines.append("")
    lines.append("Verified:")
    lines.append(_display(profile.verified))
    lines.append("")
    lines.append("Private:")
    lines.append(_display(profile.private))
    lines.append("")
    lines.append("Business account:")
    lines.append(_display(profile.business_account))
    lines.append("")
    lines.append("Business category:")
    lines.append(_display(profile.business_category_name))
    lines.append("")
    lines.append("Has external URL:")
    lines.append(_yes_no(profile.external_url))
    lines.append("")
    lines.append("Has public email:")
    lines.append(_yes_no(profile.public_email))
    lines.append("")
    lines.append("Has public phone:")
    lines.append(_yes_no(profile.public_phone_number))
    lines.append("")
    lines.append("Latest captions and hashtags:")
    lines.extend(_latest_posts_lines(profile.raw_data))
    lines.append("")
    return lines


def _latest_posts_lines(raw_data: dict[str, Any]) -> list[str]:
    posts = _extract_posts(raw_data)
    if not posts:
        return ["Не указано"]

    lines: list[str] = []
    selected_posts = [post for post in posts if isinstance(post, dict)][:MAX_CAPTIONS_PER_PROFILE]

    for index, post in enumerate(selected_posts, start=1):
        caption = _post_caption(post)
        hashtags = _post_hashtags(post)

        lines.append("")
        lines.append(f"{index}.")
        lines.append("Caption:")
        lines.append(caption or "No caption")
        lines.append("Hashtags:")
        lines.extend(_list_lines(hashtags))

    return lines or ["Не указано"]


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
            return _trim_text(str(value).strip())
    return ""


def _post_hashtags(post: dict[str, Any]) -> list[str]:
    value = post.get("hashtags")
    if isinstance(value, list):
        return [_trim_text(str(item).strip()) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [_trim_text(value.strip())]
    return []


def _list_lines(values: list[str]) -> list[str]:
    if not values:
        return ["Не указано"]
    return [f"- {value}" for value in values if value]


def _display(value: object) -> str:
    if value is None or value == "":
        return "Не указано"
    return str(value)


def _yes_no(value: object) -> str:
    return "Да" if value else "Нет"


def _trim_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = value.strip()
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    return f"{text[: MAX_TEXT_LENGTH - 3].rstrip()}..."
