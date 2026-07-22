import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    apify_api_token: str = os.getenv("APIFY_API_TOKEN", "")
    apify_instagram_actor_id: str = os.getenv("APIFY_INSTAGRAM_ACTOR_ID", "")

    google_service_account_file: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "service_account.json",
    )
    google_spreadsheet_id: str = os.getenv("GOOGLE_SPREADSHEET_ID", "")
    google_source_sheet: str = os.getenv("GOOGLE_SOURCE_SHEET", "Input")
    google_results_sheet: str = os.getenv("GOOGLE_RESULTS_SHEET", "Results")

    search_api_key: str = os.getenv("SEARCH_API_KEY", "")
    search_engine_id: str = os.getenv("SEARCH_ENGINE_ID", "")


settings = Settings()
