from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse


_COLUMN_RE = re.compile(r"^[A-Za-z]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]+$")
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}
_RESERVED_PATHS = {
    "accounts",
    "direct",
    "explore",
    "p",
    "reel",
    "reels",
    "stories",
    "tv",
}


class SheetsServiceError(Exception):
    pass


def normalize_instagram_profile_url(value: str) -> str | None:
    raw_value = value.strip()
    if not raw_value:
        return None

    if raw_value.startswith("@"):
        username = raw_value[1:]
        return _normalize_username(username)

    parsed_value = raw_value
    if "://" not in parsed_value and parsed_value.lower().startswith(
        ("instagram.com/", "www.instagram.com/")
    ):
        parsed_value = f"https://{parsed_value}"

    parsed = urlparse(parsed_value)
    if parsed.netloc:
        host = parsed.netloc.lower()
        if host not in _INSTAGRAM_HOSTS:
            return None

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) != 1:
            return None

        username = path_parts[0]
        if username.lower() in _RESERVED_PATHS:
            return None
        return _normalize_username(username)

    if "/" in raw_value or "?" in raw_value or "#" in raw_value:
        return None

    return _normalize_username(raw_value)


def extract_instagram_urls_from_column(values: list[list[str]]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for row in values:
        if not row:
            continue

        normalized_url = normalize_instagram_profile_url(str(row[0]))
        if normalized_url is None or normalized_url in seen:
            continue

        seen.add(normalized_url)
        urls.append(normalized_url)

    return urls


class SheetsService:
    def __init__(
        self,
        service_account_file: str,
        spreadsheet_id: str,
        source_sheet: str,
        source_column: str = "B",
    ) -> None:
        self.service_account_file = service_account_file
        self.spreadsheet_id = spreadsheet_id
        self.source_sheet = source_sheet
        self.source_column = source_column

    def get_instagram_urls(self) -> list[str]:
        self._validate_settings()

        try:
            from src.integrations.google_sheets import GoogleSheetsClient, SheetsError

            client = GoogleSheetsClient.from_service_account_file(self.service_account_file)
            spreadsheet = client.open_by_id(self.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.source_sheet)
            column_range = f"{self.source_column}:{self.source_column}"
            values = worksheet.get_values(column_range)
        except ImportError as e:
            raise SheetsServiceError("Не установлены зависимости для Google Sheets.") from e
        except SheetsError as e:
            if "must not be an Office file" in str(e):
                raise SheetsServiceError(
                    "Указанный файл является Office/Excel-файлом, а не нативной Google Таблицей. "
                    "Откройте файл в Google Sheets и сохраните/преобразуйте его как Google Таблицу, "
                    "затем укажите ID этой таблицы в GOOGLE_SPREADSHEET_ID."
                ) from e
            raise SheetsServiceError(f"Не удалось прочитать Google Sheets: {e}") from e

        return extract_instagram_urls_from_column(values)

    def _validate_settings(self) -> None:
        if _has_service_account_json():
            pass
        elif not self.service_account_file:
            raise SheetsServiceError("Не задан GOOGLE_SERVICE_ACCOUNT_FILE.")
        elif not Path(self.service_account_file).is_file():
            raise SheetsServiceError("Файл service account не найден.")

        if not self.spreadsheet_id:
            raise SheetsServiceError("Не задан GOOGLE_SPREADSHEET_ID.")

        if not self.source_sheet:
            raise SheetsServiceError("Не задан GOOGLE_SOURCE_SHEET.")

        if not self.source_column or not _COLUMN_RE.fullmatch(self.source_column):
            raise SheetsServiceError("GOOGLE_SOURCE_COLUMN должен быть буквенным обозначением колонки.")

        self.source_column = self.source_column.upper()


def _normalize_username(username: str) -> str | None:
    username = username.strip()
    if not username or not _USERNAME_RE.fullmatch(username):
        return None
    return f"https://www.instagram.com/{username}/"


def _has_service_account_json() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip())
