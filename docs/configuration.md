# Конфигурация

Проект читает настройки из `.env` через `python-dotenv`. Шаблон находится в `.env.example`.

## OpenAI-compatible API

Используется для structured output на этапах Ideal Profile, Matcher и Personalized Offers.

Переменные:

- `OPENAI_API_KEY` — API-ключ.
- `OPENAI_BASE_URL` — base URL совместимого API. В шаблоне указан ProxyAPI endpoint.
- `OPENAI_MODEL` — модель для LLM-вызовов.
- `OPENAI_REQUEST_TIMEOUT_SECONDS` — timeout LLM-запросов.

Секреты не выводятся в лог и не сохраняются в JSON.

## Apify

Используется для получения данных Instagram-профилей.

Переменные:

- `APIFY_API_TOKEN` — токен Apify.
- `APIFY_ACTOR_ID` — Actor ID, например `apify~instagram-scraper`.
- `APIFY_SOURCE_PROFILES_LIMIT` — сколько референсных профилей брать из исходного списка.
- `APIFY_REQUEST_TIMEOUT_SECONDS` — timeout Apify-запроса.

Если нужно обработать весь исходный список, укажите число больше количества URL в таблице. Пустое значение использует default `3`, а `0` останавливает запуск.

## Brave Search

Используется для поиска новых кандидатов.

Переменные:

- `BRAVE_SEARCH_API_KEY` — ключ Brave Search API.
- `SEARCH_ENGINE_ID` — присутствует в конфигурации, но текущий Brave Search flow его не использует.

Запросы строятся из ниши и required topics идеального профиля. Максимум запросов задаётся в коде `DiscoveryQueryBuilder`.

## Google Sheets

Используется для чтения референсов и экспорта итогов.

Переменные:

- `GOOGLE_SERVICE_ACCOUNT_FILE` — путь к service account JSON.
- `GOOGLE_SERVICE_ACCOUNT_JSON` — содержимое service account JSON для деплоя без файла; имеет приоритет над `GOOGLE_SERVICE_ACCOUNT_FILE`.
- `GOOGLE_SPREADSHEET_ID` — ID существующей Google-таблицы.
- `GOOGLE_SHEET_URL` — ссылка на итоговую таблицу для web-интерфейса.
- `GOOGLE_SOURCE_SHEET` — лист с исходными блогерами.
- `GOOGLE_SOURCE_COLUMN` — колонка с Instagram URL или username.
- `GOOGLE_RESULTS_SHEET` — сохранена в настройках, но текущий экспорт пишет в фиксированные русскоязычные листы.

## Подготовка Google Sheets

1. Создать или открыть нативную Google-таблицу.
2. Создать лист-источник, например `Input` или `Референсные блогеры`.
3. В указанную колонку добавить Instagram URL или username.
4. Выдать service account доступ к таблице.
5. Указать ID таблицы в `.env`.

Важно: файл должен быть нативной Google Таблицей, а не Office/Excel-файлом.

## Проверка конфигурации

Минимальная команда запуска:

```powershell
python -m src.main
```

Для проверки без внешних API используйте unit-тесты:

```powershell
python -m pytest -v
```
