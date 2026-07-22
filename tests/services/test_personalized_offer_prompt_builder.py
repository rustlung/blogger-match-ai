from __future__ import annotations

from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.personalized_offer_prompt_builder import PersonalizedOfferPromptBuilder


def test_personalized_offer_system_prompt_contains_no_fabrication_rules() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_system_prompt()

    assert "не придумывай просмотренные публикации" in prompt.lower()
    assert "метрики вовлеченности" in prompt.lower()
    assert "пиши все текстовые поля" in prompt.lower()
    assert "не раскрывай работу matcher" in prompt.lower()


def test_personalized_offer_system_prompt_defaults_to_barter_without_price_list_request() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_system_prompt().lower()

    assert "по умолчанию предлагай бартерное сотрудничество" in prompt
    assert "не проси прайс-лист" in prompt
    assert "не спрашивай стоимость интеграции" in prompt
    assert "не предполагай оплату" in prompt


def test_personalized_offer_system_prompt_keeps_review_first_message_light() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_system_prompt().lower()

    assert "первое сообщение должно быть легким" in prompt
    assert "не проси одновременно прайс" in prompt
    assert "стоимость и условия" in prompt
    assert "можно оставить для следующих сообщений" in prompt


def test_personalized_offer_system_prompt_guides_review_notes_to_barter_checks() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_system_prompt().lower()

    assert "manual_review_notes" in prompt
    assert "проверить возможность бартерного сотрудничества" in prompt
    assert "подходящие форматы" in prompt
    assert "интересные товары" in prompt
    assert "контакт для связи" in prompt
    assert "er только при необходимости" in prompt


def test_personalized_offer_system_prompt_preserves_cautious_matcher_inferences() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_system_prompt().lower()

    assert "вероятно" in prompt
    assert "можно ожидать" in prompt
    assert "предположительно" in prompt
    assert "скорее всего" in prompt
    assert "не превращай вывод в утверждение" in prompt


def test_personalized_offer_system_prompt_requires_varied_message_openings() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_system_prompt().lower()

    assert "варьируй начало сообщения" in prompt
    assert "обратили внимание" in prompt
    assert "нам понравилось" in prompt


def test_personalized_offer_user_prompt_contains_useful_fields_without_raw_data_or_secrets() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_user_prompt(
        ideal_profile=_ideal_profile(),
        candidate_profile=_blogger(),
        match_result=_match_result(),
    )

    assert "семейный лайфстайл" in prompt
    assert "creator" in prompt
    assert "Short bio" in prompt
    assert "Тематика совпадает" in prompt
    assert "Caption: Пост о семейном утре" in prompt
    assert "raw_data" not in prompt
    assert "childPosts" not in prompt
    assert "imageUrl" not in prompt
    assert "api_key" not in prompt.lower()


def test_personalized_offer_user_prompt_preserves_cautious_matcher_wording() -> None:
    prompt = PersonalizedOfferPromptBuilder().build_user_prompt(
        ideal_profile=_ideal_profile(),
        candidate_profile=_blogger(),
        match_result=_match_result(
            strengths=["Вероятно, профиль подходит по домашней подаче."],
            risks=["Скорее всего, ER нужно подтвердить отдельно."],
            match_summary="Предположительно формат может подойти, но данных мало.",
        ),
    )

    assert "Вероятно, профиль подходит по домашней подаче." in prompt
    assert "Скорее всего, ER нужно подтвердить отдельно." in prompt
    assert "Предположительно формат может подойти" in prompt


def _ideal_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(niche="семейный лайфстайл", required_topics=["семья"])


def _blogger() -> BloggerProfile:
    return BloggerProfile(
        input_url="https://www.instagram.com/creator/",
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        biography="Short bio",
        followers_count=5000,
        business_account=True,
        raw_data={
            "latestPosts": [
                {
                    "caption": "Пост о семейном утре",
                    "hashtags": ["family"],
                    "imageUrl": "https://images.example/post.jpg",
                    "childPosts": [{"caption": "hidden"}],
                }
            ],
            "api_key": "secret",
        },
    )


def _match_result(
    *,
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    match_summary: str = "Кандидат подходит.",
) -> BloggerMatchResult:
    return BloggerMatchResult(
        profile_url="https://www.instagram.com/creator/",
        username="creator",
        final_score=82,
        decision=MatchDecision.RECOMMENDED,
        region_status=RegionStatus.TARGET,
        region_confidence=80,
        detected_region="Россия",
        strengths=strengths or ["Тематика совпадает."],
        risks=risks or [],
        rejection_reasons=[],
        match_summary=match_summary,
        criteria_scores=_criteria_scores(),
    )


def _criteria_scores() -> MatchCriteriaScores:
    return MatchCriteriaScores(
        thematic_fit=_criterion(),
        audience_fit=_criterion(),
        geography_fit=_criterion(),
        language_fit=_criterion(),
        account_size_fit=_criterion(),
        engagement_fit=_criterion(),
        content_style_fit=_criterion(),
        commercial_fit=_criterion(),
    )


def _criterion() -> MatchCriterionScore:
    return MatchCriterionScore(score=80, confidence=70, reason="Тестовая причина.")
