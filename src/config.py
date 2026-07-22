import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    OPENAI_REQUEST_TIMEOUT_SECONDS: float = _get_float("OPENAI_REQUEST_TIMEOUT_SECONDS", 120.0)
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    openai_request_timeout_seconds: float = _get_float("OPENAI_REQUEST_TIMEOUT_SECONDS", 120.0)

    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
    APIFY_ACTOR_ID: str = os.getenv("APIFY_ACTOR_ID", "apify~instagram-scraper")
    APIFY_SOURCE_PROFILES_LIMIT: int = _get_int("APIFY_SOURCE_PROFILES_LIMIT", 3)
    APIFY_REQUEST_TIMEOUT_SECONDS: float = _get_float("APIFY_REQUEST_TIMEOUT_SECONDS", 300.0)

    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "service_account.json",
    )
    GOOGLE_SPREADSHEET_ID: str = os.getenv("GOOGLE_SPREADSHEET_ID", "")
    GOOGLE_SOURCE_SHEET: str = os.getenv("GOOGLE_SOURCE_SHEET", "Input")
    GOOGLE_SOURCE_COLUMN: str = os.getenv("GOOGLE_SOURCE_COLUMN", "B")
    GOOGLE_RESULTS_SHEET: str = os.getenv("GOOGLE_RESULTS_SHEET", "Results")

    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_ENGINE_ID: str = os.getenv("SEARCH_ENGINE_ID", "")


settings = Settings()
