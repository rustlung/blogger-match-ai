from __future__ import annotations

from typing import Any

from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import BloggerMatchResult
from src.models.ideal_blogger_profile import IdealBloggerProfile


class PersonalizedOfferPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
Ты эксперт по influencer-маркетингу и готовишь персонализированное деловое предложение для первого контакта с Instagram-блогером.
Пиши все текстовые поля на естественном деловом русском языке.
Опирайся только на переданные IdealBloggerProfile, BloggerProfile и BloggerMatchResult.
Не придумывай просмотренные публикации, reels, stories, рекламные интеграции, метрики вовлеченности, демографию аудитории, имя блогера, бренд, продукт, бюджет, сроки или условия.
Не приписывай блогеру ценности, интересы или прошлый опыт, которых нет во входных данных.
Разделяй наблюдаемые данные, осторожные выводы и неизвестные сведения.
Matcher inference используй только как осторожный сигнал, а не как подтвержденный факт без оговорки.
Если Matcher использует формулировки "вероятно", "можно ожидать", "предположительно", "скорее всего" или похожие, сохрани осторожность и не превращай вывод в утверждение.
Учитывай decision, strengths, risks и rejection_reasons, но не раскрывай работу Matcher, внутренний score или техническую оценку в сообщении блогеру.
Для recommended подготовь уверенное, но ненавязчивое предложение со статусом ready.
Для review подготовь осторожный draft со статусом needs_review и непустыми manual_review_notes.
По умолчанию предлагай бартерное сотрудничество: не проси прайс-лист, не спрашивай стоимость интеграции и не предполагай оплату.
Не используй слово "бартер" механически в каждом сообщении; если естественнее, напиши "сотрудничество с предоставлением продукта" или похожую деловую формулировку.
Первое сообщение должно быть легким: максимум уточнить интерес к сотрудничеству и удобный контакт, если контакт не указан.
Не проси одновременно прайс, медиакит, ER, аналитику, аудиторию, кейсы, стоимость и условия; такие вопросы можно оставить для следующих сообщений.
Для manual_review_notes у review-кандидатов рекомендуй проверить возможность бартерного сотрудничества, подходящие форматы, интересные товары, ограничения, нужные дополнительные материалы, контакт для связи и ER только при необходимости.
Если возможная оплата упоминается, она должна быть дополнительной опцией, а не основной темой первого контакта.
Варьируй начало сообщения и не повторяй одинаковые конструкции вроде "Обратили внимание", "Нам понравилось" или "Хотели бы обсудить" в каждом письме.
Для rejected предложения не создаются.
Сообщение должно быть коротким, персонализированным, без шаблонной похвалы, давления, кликбейта и политических, национальных или чувствительных формулировок.
Не пиши, что сообщение создано AI.
Верни только structured output модели PersonalizedOffer.
""".strip()

    def build_user_prompt(
        self,
        ideal_profile: IdealBloggerProfile,
        candidate_profile: BloggerProfile,
        match_result: BloggerMatchResult,
    ) -> str:
        lines: list[str] = []

        lines.append("IdealBloggerProfile")
        lines.append("")
        lines.append(f"Niche: {_display(ideal_profile.niche)}")
        lines.append(f"Target gender: {_display(ideal_profile.target_gender)}")
        lines.append(f"Target age range: {_display(ideal_profile.target_age_range)}")
        lines.append(f"Followers range: {_followers_range(ideal_profile.min_followers, ideal_profile.max_followers)}")
        lines.append("Required topics:")
        lines.extend(_list_lines(ideal_profile.required_topics))
        lines.append("Excluded topics:")
        lines.extend(_list_lines(ideal_profile.excluded_topics))
        lines.append("Preferred regions:")
        lines.extend(_list_lines(ideal_profile.preferred_regions))
        lines.append("Preferred languages:")
        lines.extend(_list_lines(ideal_profile.preferred_languages))
        lines.append(f"Required brand style: {_display(ideal_profile.required_brand_style)}")

        lines.append("")
        lines.append("---------------------")
        lines.append("")
        lines.append("Candidate BloggerProfile")
        lines.append("")
        lines.append(f"Profile URL: {_display(candidate_profile.profile_url)}")
        lines.append(f"Username: {_display(candidate_profile.username)}")
        lines.append(f"Full name: {_display(candidate_profile.full_name)}")
        lines.append(f"Biography: {_display(candidate_profile.biography)}")
        lines.append(f"Followers count: {_display(candidate_profile.followers_count)}")
        lines.append(f"Posts count: {_display(candidate_profile.posts_count)}")
        lines.append(f"Verified: {_display(candidate_profile.verified)}")
        lines.append(f"Private: {_display(candidate_profile.private)}")
        lines.append(f"Business account: {_display(candidate_profile.business_account)}")
        lines.append(f"Business category: {_display(candidate_profile.business_category_name)}")
        lines.append(f"Has external URL: {_yes_no(candidate_profile.external_url)}")
        lines.append(f"Has public email: {_yes_no(candidate_profile.public_email)}")
        lines.append("Latest observable post text:")
        lines.extend(_latest_posts_lines(candidate_profile.raw_data))

        lines.append("")
        lines.append("---------------------")
        lines.append("")
        lines.append("BloggerMatchResult")
        lines.append("")
        lines.append(f"Profile URL: {_display(match_result.profile_url)}")
        lines.append(f"Username: {_display(match_result.username)}")
        lines.append(f"Decision: {match_result.decision.value}")
        lines.append(f"Final score: {match_result.final_score}")
        lines.append(f"Region status: {match_result.region_status.value}")
        lines.append(f"Detected region: {_display(match_result.detected_region)}")
        lines.append("Strengths:")
        lines.extend(_list_lines(match_result.strengths))
        lines.append("Risks:")
        lines.extend(_list_lines(match_result.risks))
        lines.append("Rejection reasons:")
        lines.extend(_list_lines(match_result.rejection_reasons))
        lines.append(f"Match summary: {_display(match_result.match_summary)}")

        return "\n".join(lines)


def _display(value: object) -> str:
    if value is None or value == "":
        return "Не указано"
    return str(value)


def _followers_range(min_followers: int | None, max_followers: int | None) -> str:
    if min_followers is None and max_followers is None:
        return "Не указано"
    if min_followers is not None and max_followers is not None:
        return f"{min_followers} - {max_followers}"
    if min_followers is not None:
        return f"От {min_followers}"
    return f"До {max_followers}"


def _list_lines(values: list[str]) -> list[str]:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ["- Не указано"]
    return [f"- {value}" for value in cleaned]


def _yes_no(value: object) -> str:
    return "Да" if value else "Нет"


def _latest_posts_lines(raw_data: dict[str, Any]) -> list[str]:
    posts = _extract_posts(raw_data)
    if not posts:
        return ["- Не указано"]

    lines: list[str] = []
    for index, post in enumerate(posts[:3], start=1):
        if not isinstance(post, dict):
            continue
        caption = _post_caption(post)
        hashtags = _post_hashtags(post)
        lines.append(f"{index}. Caption: {caption or 'No caption'}")
        lines.append("Hashtags:")
        lines.extend(_list_lines(hashtags))

    return lines or ["- Не указано"]


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
            return str(value).strip()[:500]
    return ""


def _post_hashtags(post: dict[str, Any]) -> list[str]:
    value = post.get("hashtags")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:10]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
