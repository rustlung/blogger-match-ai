# Архитектура

Проект построен как последовательный pipeline с разделением ответственности между моделями, сервисами, интеграциями и утилитами. Точка входа `src/main.py` координирует этапы, но не содержит логику работы с внешними API.

## Общая схема

```text
Reference Bloggers
↓
Apify Reference Enrichment
↓
Ideal Profile Builder
↓
Brave Search Discovery
↓
Apify Candidate Enrichment
↓
Matcher
↓
Personalized Offer Generator
↓
JSON Artifacts
↓
Google Sheets Export
```

## Основные слои

`src/models/` содержит Pydantic-модели. Они задают контракты данных между этапами и используются для structured output LLM.

`src/services/` содержит прикладные сервисы: чтение таблицы, обогащение профилей, построение промптов, LLM-запросы, поиск, матчинг, генерацию предложений и экспорт.

`src/integrations/` содержит тонкие wrappers вокруг внешних SDK. Сейчас там находится Google Sheets wrapper поверх `gspread`.

`src/utils/` содержит общие технические функции, например атомарную запись JSON и логгер.

## Поток данных

Pipeline передаёт Python-объекты между сервисами напрямую. JSON-файлы используются как runtime-артефакты выполнения, а не как основной способ обмена между этапами.

Например, после `DiscoveryService` результат сразу передаётся в `DiscoveredProfileEnrichmentService`. После `BatchMatcherService` список `BloggerMatchResult` передаётся в `BatchPersonalizedOfferService`. В конце те же объекты используются для экспорта в Google Sheets.

## Сервисы

- `SheetsService` читает исходные Instagram URL из Google Sheets.
- `ApifyService` получает данные Instagram-профилей и преобразует их в `BloggerProfile`.
- `IdealProfileService` строит `IdealProfileAnalysis`.
- `DiscoveryService` ищет новых кандидатов через Brave Search.
- `DiscoveredProfileEnrichmentService` загружает найденные профили через тот же `ApifyService`.
- `MatcherService` оценивает одного кандидата.
- `BatchMatcherService` обрабатывает список кандидатов и отделяет технические ошибки.
- `PersonalizedOfferService` генерирует одно предложение.
- `BatchPersonalizedOfferService` фильтрует `rejected`, сопоставляет профили и собирает предложения.
- `ExportService` записывает итоговые таблицы в существующую Google-таблицу.

## Structured Output

LLM-вызовы используют OpenAI SDK-compatible `chat.completions.parse` и Pydantic-модели как `response_format`. Это применяется для идеального профиля, матчинга и персонализированных предложений.

## Ошибки

Технические ошибки не превращаются в бизнес-решения. Например, ошибка LLM при матчинге сохраняется как batch error, а не как `rejected`. Это же правило применяется при генерации предложений.
