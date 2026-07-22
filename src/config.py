import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
    APIFY_INSTAGRAM_ACTOR_ID: str = os.getenv("APIFY_INSTAGRAM_ACTOR_ID", "")

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
