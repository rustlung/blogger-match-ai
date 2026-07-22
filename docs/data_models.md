# Модели данных

Ниже перечислены основные доменные модели. Полный список полей находится в `src/models/`.

## BloggerProfile

Назначение: нормализованное представление Instagram-профиля после Apify.

Основные поля:

- `profile_url`;
- `username`;
- `full_name`;
- `biography`;
- `followers_count`;
- `posts_count`;
- `business_account`;
- `business_category_name`;
- `raw_data`.

Используется на этапах Ideal Profile, Matcher и Personalized Offers. При сохранении публичных JSON и экспорте полный `raw_data` не используется как человекочитаемый результат.

## ApifyEnrichmentResult

Назначение: результат пакетной загрузки профилей.

Содержит:

- `profiles`;
- `failed_profiles`.

Используется для референсов и найденных кандидатов.

## IdealBloggerProfile

Назначение: описание целевого блогера, построенное по референсам.

Основные поля:

- `niche`;
- `target_gender`;
- `target_age_range`;
- `min_followers`;
- `max_followers`;
- `required_topics`;
- `excluded_topics`;
- `preferred_regions`;
- `preferred_languages`;
- `required_brand_style`.

## IdealProfileAnalysis

Назначение: обёртка над идеальным профилем с объяснением и ограничениями данных.

Используется после LLM-анализа референсов и сохраняется в `ideal_blogger_profile.json`.

## DiscoveryResult

Назначение: результат Brave Search discovery.

Содержит поисковые запросы, найденных кандидатов и общий счётчик кандидатов.

## BloggerMatchResult

Назначение: structured output Matcher для одного кандидата.

Основные поля:

- `profile_url`;
- `username`;
- `final_score`;
- `decision`;
- `region_status`;
- `strengths`;
- `risks`;
- `rejection_reasons`;
- `match_summary`;
- `criteria_scores`.

В модели есть бизнес-инварианты: например, `non_target` должен быть `rejected` с `final_score = 0`.

## BatchMatchResult

Назначение: результат пакетного матчинга.

Содержит успешные `matches`, технические `errors` и счётчики. Ошибка LLM или сопоставления не превращается в `rejected`.

## PersonalizedOffer

Назначение: черновик первого сообщения блогеру.

Основные поля:

- `match_decision`;
- `match_score`;
- `offer_status`;
- `personalization_points`;
- `collaboration_angle`;
- `proposed_format`;
- `subject`;
- `message`;
- `manual_review_notes`.

Для `rejected` эта модель не создаётся. Для `review` требуется статус `needs_review` и непустые заметки.

## BatchPersonalizedOfferResult

Назначение: результат пакетной генерации предложений.

Содержит созданные предложения, технические ошибки и счётчики eligible/skipped/success/failed.
