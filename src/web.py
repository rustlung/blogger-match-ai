from __future__ import annotations

import html
import json
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from src.config import settings
from src.utils.logger import logger


app = FastAPI(title="Blogger Match AI")
_pipeline_lock = threading.Lock()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    sheet_link = _sheet_link_html()
    body = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Blogger Match AI</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #1f2937;
      background: #f8fafc;
    }}
    main {{
      max-width: 760px;
      margin: 56px auto;
      padding: 32px;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }}
    h1 {{
      margin-top: 0;
      font-size: 32px;
    }}
    p {{
      line-height: 1.55;
    }}
    button, .button {{
      display: inline-block;
      padding: 12px 18px;
      border: 0;
      border-radius: 6px;
      color: #ffffff;
      background: #2563eb;
      font-size: 16px;
      text-decoration: none;
      cursor: pointer;
    }}
    .muted {{
      color: #6b7280;
    }}
    .warning {{
      padding: 12px 14px;
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Blogger Match AI</h1>
    <p>Демонстрационный web-интерфейс для запуска анализа Instagram-блогеров по текущему pipeline проекта.</p>
    <p class="warning">Выполнение может занять несколько минут и использует внешние API.</p>
    <form action="/run" method="post">
      <button type="submit">Запустить анализ</button>
    </form>
    {sheet_link}
    <p class="muted">Если анализ уже запущен, повторный запуск будет отклонён до завершения текущего.</p>
  </main>
</body>
</html>
"""
    return HTMLResponse(body)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/run", response_class=HTMLResponse)
def run_analysis() -> HTMLResponse:
    if not _pipeline_lock.acquire(blocking=False):
        return _page(
            title="Анализ уже выполняется",
            paragraphs=["Анализ уже выполняется. Дождитесь завершения текущего запуска."],
            status_code=409,
        )

    try:
        exit_code = _run_pipeline()
        if exit_code != 0:
            logger.warning("Pipeline finished with non-zero exit code: exit_code=%s", exit_code)
            return _page(
                title="Анализ не завершился",
                paragraphs=[
                    "Pipeline остановился с ошибкой. Проверьте настройки окружения и логи приложения.",
                ],
                status_code=500,
            )

        summary = _load_run_summary()
        return _page(
            title="Анализ завершён",
            paragraphs=["Pipeline успешно выполнен.", *summary],
        )
    except Exception as exc:
        logger.exception("Pipeline run failed: error_type=%s", type(exc).__name__)
        return _page(
            title="Ошибка запуска",
            paragraphs=[
                "Не удалось выполнить анализ. Технические детали записаны в лог приложения.",
            ],
            status_code=500,
        )
    finally:
        _pipeline_lock.release()


def _run_pipeline() -> int:
    from src.main import main

    return main()


def _load_run_summary() -> list[str]:
    summary: list[str] = []
    match_results = _read_json(Path("results/match_results.json"))
    offer_results = _read_json(Path("results/personalized_offers.json"))

    if match_results:
        summary.append(f"Проанализировано кандидатов: {_display(match_results.get('successful_matches'))}.")
        summary.append(f"Технических ошибок Matcher: {_display(match_results.get('failed_matches'))}.")

    if offer_results:
        summary.append(f"Сформировано предложений: {_display(offer_results.get('successful_offers'))}.")
        summary.append(f"Пропущено отклонённых кандидатов: {_display(offer_results.get('skipped_rejected'))}.")

    if not summary:
        summary.append("Краткая статистика недоступна: runtime JSON ещё не найден.")

    return summary


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read run summary: path=%s error_type=%s", path, type(exc).__name__)
        return {}
    return payload if isinstance(payload, dict) else {}


def _sheet_link_html() -> str:
    if not settings.GOOGLE_SHEET_URL:
        return ""
    url = html.escape(settings.GOOGLE_SHEET_URL, quote=True)
    return f'<p><a href="{url}" target="_blank" rel="noopener">Открыть итоговую Google-таблицу</a></p>'


def _page(title: str, paragraphs: list[str], status_code: int = 200) -> HTMLResponse:
    sheet_link = _sheet_link_html()
    paragraph_html = "\n".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)
    body = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} — Blogger Match AI</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #1f2937;
      background: #f8fafc;
    }}
    main {{
      max-width: 760px;
      margin: 56px auto;
      padding: 32px;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }}
    h1 {{
      margin-top: 0;
    }}
    p {{
      line-height: 1.55;
    }}
    a {{
      color: #2563eb;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    {paragraph_html}
    {sheet_link}
    <p><a href="/">Вернуться на главную</a></p>
  </main>
</body>
</html>
"""
    return HTMLResponse(body, status_code=status_code)


def _display(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)
