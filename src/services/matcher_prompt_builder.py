from __future__ import annotations

from src.models.blogger import BloggerProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile


class MatcherPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
Ты эксперт по influencer-маркетингу и оцениваешь одного Instagram-блогера на соответствие идеальному профилю.
Используй только предоставленные данные IdealBloggerProfile и BloggerProfile.
Не выдумывай отсутствующие сведения, метрики, охваты, engagement rate, демографию, контакты или регион.
Разделяй наблюдаемые факты и осторожные выводы.
Для каждого критерия укажи score, confidence и короткую причину.
Если данных недостаточно, снижай confidence и явно указывай это в reason или risks.
Не завышай final_score при недостатке данных.
Целевой рынок: Россия.
География является обязательным бизнес-критерием.
Если есть надежные признаки Украины или преимущественно украинского рынка: region_status=non_target, decision=rejected, final_score=0, rejection_reasons непустой.
Если есть надежные признаки российского рынка: region_status=target.
Если регион надежно не определяется: region_status=unknown, detected_region=null или осторожное описание, не отклоняй автоматически только из-за отсутствия региона, добавь risk и снизь geography confidence.
Не определяй регион только по русскому языку.
Не считай русскоязычный профиль автоматически российским.
Не делай вывод о стране без подтверждающих сигналов.
Не используй политические или национальные оценки; нужна только деловая проверка соответствия целевому рынку.
Не возвращай противоречивые результаты: non_target не может быть recommended, Украина не может иметь final_score выше 0.
Все текстовые аналитические поля должны быть на естественном деловом русском языке.
Верни только structured output модели BloggerMatchResult.
""".strip()

    def build_user_prompt(
        self,
        ideal_profile: IdealBloggerProfile,
        candidate_profile: BloggerProfile,
    ) -> str:
        lines: list[str] = []
        lines.append("IdealBloggerProfile")
        lines.append("")
        lines.append(f"Niche: {_display(ideal_profile.niche)}")
        lines.append(f"Target gender: {_display(ideal_profile.target_gender)}")
        lines.append(f"Target age range: {_display(ideal_profile.target_age_range)}")
        lines.append(f"Min followers: {_display(ideal_profile.min_followers)}")
        lines.append(f"Max followers: {_display(ideal_profile.max_followers)}")
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
        lines.append(f"Follows count: {_display(candidate_profile.follows_count)}")
        lines.append(f"Posts count: {_display(candidate_profile.posts_count)}")
        lines.append(f"Verified: {_display(candidate_profile.verified)}")
        lines.append(f"Private: {_display(candidate_profile.private)}")
        lines.append(f"Business account: {_display(candidate_profile.business_account)}")
        lines.append(f"Business category: {_display(candidate_profile.business_category_name)}")
        lines.append(f"Has external URL: {_yes_no(candidate_profile.external_url)}")
        lines.append(f"Has public email: {_yes_no(candidate_profile.public_email)}")
        lines.append(f"Has public phone: {_yes_no(candidate_profile.public_phone_number)}")

        return "\n".join(lines)


def _display(value: object) -> str:
    if value is None or value == "":
        return "Не указано"
    return str(value)


def _list_lines(values: list[str]) -> list[str]:
    if not values:
        return ["- Не указано"]
    return [f"- {value}" for value in values if value]


def _yes_no(value: object) -> str:
    return "Да" if value else "Нет"
