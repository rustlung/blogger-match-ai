# Pipeline

Этот документ описывает этапы выполнения `python -m src.main`. Конфигурация и подготовка ключей вынесены в [configuration.md](configuration.md).

## 1. Чтение референсных блогеров

Назначение: получить исходный список Instagram-профилей из Google Sheets.

Вход: `GOOGLE_SPREADSHEET_ID`, `GOOGLE_SOURCE_SHEET`, `GOOGLE_SOURCE_COLUMN`.

Выход: список нормализованных URL вида `https://www.instagram.com/username/`.

Сервис: `SheetsService`.

Модель: на этом этапе используются строки URL, без доменной модели.

## 2. Обогащение референсов через Apify

Назначение: получить профильные данные по исходным блогерам.

Вход: список URL, ограниченный `APIFY_SOURCE_PROFILES_LIMIT`.

Выход: `ApifyEnrichmentResult` с успешными `BloggerProfile` и `FailedProfile`.

Сервис: `ApifyService`.

Артефакт: `results/apify_raw_response.json` содержит последний raw dataset Apify.

## 3. Построение идеального профиля

Назначение: обобщить успешные референсы в профиль подходящего блогера.

Вход: список `BloggerProfile`.

Выход: `IdealProfileAnalysis`, внутри которого находится `IdealBloggerProfile`.

Сервисы: `IdealProfilePromptBuilder`, `IdealProfileService`.

Артефакт: `results/ideal_blogger_profile.json`.

## 4. Поиск кандидатов

Назначение: найти новые Instagram-профили по темам из идеального профиля.

Вход: `IdealBloggerProfile`, usernames референсных блогеров.

Выход: `DiscoveryResult`.

Сервисы: `DiscoveryQueryBuilder`, `BraveSearchClient`, `DiscoveryService`.

Артефакт: `results/discovered_candidates.json`.

## 5. Обогащение найденных кандидатов

Назначение: загрузить найденные профили через Apify.

Вход: URL из `DiscoveryResult`.

Выход: `ApifyEnrichmentResult` с `BloggerProfile` кандидатов.

Сервис: `DiscoveredProfileEnrichmentService`.

Артефакт: `results/discovered_profiles.json`.

## 6. Matcher

Назначение: оценить каждого кандидата относительно идеального профиля.

Вход: `IdealBloggerProfile`, список `BloggerProfile`.

Выход: `BatchMatchResult` со списком `BloggerMatchResult` и техническими ошибками.

Сервисы: `MatcherPromptBuilder`, `MatcherService`, `BatchMatcherService`, `LLMService`.

Артефакт: `results/match_results.json`.

## 7. Personalized Offers

Назначение: подготовить черновики бартерных предложений.

Вход: `IdealBloggerProfile`, профили кандидатов, `BloggerMatchResult`.

Выход: `BatchPersonalizedOfferResult`.

Сервисы: `PersonalizedOfferPromptBuilder`, `PersonalizedOfferService`, `BatchPersonalizedOfferService`.

Правило: для `rejected` предложения не генерируются.

Артефакт: `results/personalized_offers.json`.

## 8. Экспорт в Google Sheets

Назначение: записать человекочитаемые результаты в существующую книгу.

Вход: результаты предыдущих этапов из памяти.

Выход: обновлённые рабочие листы Google Sheets.

Сервис: `ExportService`.

Исходный лист `GOOGLE_SOURCE_SHEET` не изменяется.
