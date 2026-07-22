# Blogger Match AI

Blogger Match AI — консольный Python-проект для подбора Instagram-блогеров по референсным профилям. Он читает исходный список из Google Sheets, строит портрет подходящего блогера, ищет похожих кандидатов, оценивает их и готовит черновики персонализированных бартерных предложений.

Проект решает практическую задачу influencer-маркетинга: быстрее перейти от набора удачных референсов к списку новых кандидатов, понятной оценке соответствия и таблице результатов для ручной проверки.

## Возможности

- чтение референсных Instagram-профилей из существующей Google-таблицы;
- обогащение профилей через Apify Instagram Actor;
- построение `IdealBloggerProfile` через structured output LLM;
- поиск новых кандидатов через Brave Search;
- оценка кандидатов через Matcher;
- генерация персонализированных предложений для `recommended` и `review`;
- сохранение runtime JSON в `results/`;
- экспорт итогов в рабочие листы той же Google-таблицы.

## Pipeline

```text
Google Sheets
-> Apify reference profiles
-> Ideal Profile Builder
-> Brave Discovery
-> Apify candidate profiles
-> Matcher
-> Personalized Offers
-> JSON results
-> Google Sheets export
```

Подробное описание этапов: [docs/pipeline.md](docs/pipeline.md). Архитектурная схема: [docs/architecture.md](docs/architecture.md).

## Технологии

- Python 3.12;
- Pydantic для моделей и structured output;
- OpenAI SDK-compatible client;
- Apify Actor API;
- Brave Search API;
- Google Sheets через service account и `gspread`;
- `python-dotenv`, `httpx`, `pytest`.

## Структура

Основной код находится в `src/`: модели, сервисы, интеграции, утилиты и точка входа `src/main.py`. Runtime-результаты пишутся в `results/`, а исходные локальные данные можно хранить в `data/`. Краткое описание каталогов: [docs/project_structure.md](docs/project_structure.md).

## Быстрый запуск

1. Создать и активировать виртуальное окружение.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Установить зависимости.

```powershell
pip install -r requirements.txt
```

3. Создать `.env` на основе `.env.example` и заполнить ключи.

```powershell
Copy-Item .env.example .env
```

4. Поместить service account файл, например `service_account.json`, в корень проекта.

5. Запустить полный pipeline.

```powershell
python -m src.main
```

Настройки подробно описаны в [docs/configuration.md](docs/configuration.md).

## Web-интерфейс

Для локальной демонстрации можно запустить тонкий FastAPI-слой поверх существующего pipeline:

```powershell
uvicorn src.web:app --host 0.0.0.0 --port 8000
```

После запуска откройте `http://localhost:8000`. Кнопка «Запустить анализ» вызывает тот же полный pipeline, что и `python -m src.main`; повторный запуск блокируется, пока текущий анализ не завершён.

Дополнительная переменная для интерфейса:

- `GOOGLE_SHEET_URL` — публичная или рабочая ссылка на итоговую Google-таблицу, отображается только в HTML.

## Google Sheets

Проект использует существующую Google-таблицу из `GOOGLE_SPREADSHEET_ID`. Лист `GOOGLE_SOURCE_SHEET` является источником референсных блогеров и программой не изменяется.

При экспорте автоматически создаются и обновляются рабочие листы:

- `Титульный лист`;
- `Идеальный профиль`;
- `Найденные кандидаты`;
- `Сопоставление`;
- `Предложения`;
- `Статистика`.

Для локального запуска используется `GOOGLE_SERVICE_ACCOUNT_FILE`. На Render удобнее задать `GOOGLE_SERVICE_ACCOUNT_JSON` целиком как secret environment variable. В обоих случаях service account нужно расшарить доступ к Google-таблице: откройте настройки доступа таблицы и добавьте email сервисного аккаунта с правами редактора.

## Render

Проект подготовлен для Render Web Service через `render.yaml`.

Build Command:

```text
pip install -r requirements.txt
```

Start Command:

```text
uvicorn src.web:app --host 0.0.0.0 --port $PORT
```

Health Check Path:

```text
/health
```

В Render нужно добавить переменные окружения из `.env.example`: ключи OpenAI-compatible provider, Apify, Brave Search, Google Sheets ID и параметры источника. Для credentials используйте `GOOGLE_SERVICE_ACCOUNT_JSON`, а не файл. Секреты не нужно помещать в `render.yaml`.

На бесплатном тарифе Render приложение может некоторое время просыпаться после простоя; первый запрос к web-интерфейсу из-за этого бывает медленнее.

## Результаты

JSON-файлы сохраняются в `results/` и не предназначены для коммита:

- `ideal_blogger_profile.json`;
- `discovered_candidates.json`;
- `discovered_profiles.json`;
- `match_results.json`;
- `personalized_offers.json`;
- `apify_raw_response.json`.

Итоговая Google-таблица содержит человекочитаемые русскоязычные листы. Внутренние enum-значения переводятся при экспорте, например `recommended` отображается как `Рекомендован`.

## Ограничения

Проект работает с Instagram-профилями и зависит от качества референсов, доступности внешних API и полноты открытых данных. Решения `review`, неопределённые регионы, ER и бартерные условия требуют ручной проверки.

Подробнее: [docs/limitations.md](docs/limitations.md).

## Документация

- [Архитектура](docs/architecture.md)
- [Pipeline](docs/pipeline.md)
- [Структура проекта](docs/project_structure.md)
- [Конфигурация](docs/configuration.md)
- [Модели данных](docs/data_models.md)
- [Ограничения](docs/limitations.md)
- [Направления развития](docs/future_improvements.md)
