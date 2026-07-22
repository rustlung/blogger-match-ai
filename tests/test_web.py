from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from src import web


def test_health_returns_status_without_running_pipeline(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(web, "_run_pipeline", lambda: calls.append("run") or 0)

    response = TestClient(web.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert calls == []


def test_index_renders_russian_demo_page_with_run_button_and_sheet_link(monkeypatch) -> None:
    monkeypatch.setattr(web, "settings", SimpleNamespace(GOOGLE_SHEET_URL="https://docs.google.com/spreadsheets/d/test"))

    response = TestClient(web.app).get("/")

    assert response.status_code == 200
    assert "Blogger Match AI" in response.text
    assert "Запустить анализ" in response.text
    assert "может занять несколько минут" in response.text
    assert "https://docs.google.com/spreadsheets/d/test" in response.text


def test_run_rejects_second_pipeline_start_when_analysis_is_already_running() -> None:
    assert web._pipeline_lock.acquire(blocking=False)
    try:
        response = TestClient(web.app).post("/run")
    finally:
        web._pipeline_lock.release()

    assert response.status_code == 409
    assert "Анализ уже выполняется. Дождитесь завершения текущего запуска" in response.text


def test_run_returns_success_page_with_mocked_pipeline(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(web, "_run_pipeline", lambda: calls.append("run") or 0)
    monkeypatch.setattr(
        web,
        "_load_run_summary",
        lambda: ["Проанализировано кандидатов: 2.", "Сформировано предложений: 1."],
    )

    response = TestClient(web.app).post("/run")

    assert response.status_code == 200
    assert calls == ["run"]
    assert "Анализ завершён" in response.text
    assert "Проанализировано кандидатов: 2." in response.text
    assert "Сформировано предложений: 1." in response.text


def test_run_returns_readable_error_page_when_mocked_pipeline_raises(monkeypatch) -> None:
    def fail() -> int:
        raise RuntimeError("external provider failed")

    monkeypatch.setattr(web, "_run_pipeline", fail)

    response = TestClient(web.app).post("/run")

    assert response.status_code == 500
    assert "Не удалось выполнить анализ" in response.text
    assert "external provider failed" not in response.text


def test_run_lock_is_released_after_mocked_pipeline_error(monkeypatch) -> None:
    def fail() -> int:
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(web, "_run_pipeline", fail)

    response = TestClient(web.app).post("/run")

    assert response.status_code == 500
    assert web._pipeline_lock.acquire(blocking=False)
    try:
        pass
    finally:
        web._pipeline_lock.release()
