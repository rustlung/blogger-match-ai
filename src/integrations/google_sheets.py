from __future__ import annotations

from typing import Any

import gspread
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, GSpreadException


class SheetsError(Exception):
    """Base Google Sheets integration error."""

    pass


class SheetsAuthError(SheetsError):
    """Authorization, service account, scope, or permission error."""

    pass


class SpreadsheetNotFound(SheetsError):
    """Spreadsheet was not found or is not available."""

    pass


class WorksheetNotFound(SheetsError):
    """Worksheet was not found."""

    pass


class RowNotFound(SheetsError):
    """Row was not found."""

    pass


class InvalidHeaderError(SheetsError):
    """Unknown header for strict row operations."""

    pass


class GoogleApiError(SheetsError):
    """Google Sheets API or gspread error."""

    pass


_DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _wrap_api(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DefaultCredentialsError as e:
            raise SheetsAuthError(f"Auth failed: {e}") from e
        except APIError as e:
            msg = _api_error_message(e)
            if "PERMISSION_DENIED" in str(e) or "401" in str(e) or "403" in str(e):
                raise SheetsAuthError(f"Auth/permission: {msg}") from e
            raise GoogleApiError(f"Google API: {msg}") from e
        except GSpreadException as e:
            err_str = str(e).lower()
            if "permission" in err_str or "auth" in err_str or "401" in err_str or "403" in err_str:
                raise SheetsAuthError(f"Auth: {e}") from e
            raise GoogleApiError(f"API: {e}") from e
        except SheetsError:
            raise
        except Exception as e:
            raise GoogleApiError(f"Unexpected: {e}") from e

    return wrapper


def _api_error_message(error: APIError) -> str:
    response = getattr(error, "response", None)

    if isinstance(response, dict):
        return str(response.get("error", {}).get("message", str(error)))

    try:
        payload = response.json() if response is not None else {}
    except ValueError:
        payload = {}

    if isinstance(payload, dict):
        message = payload.get("error", {}).get("message")
        if message:
            return str(message)

    return str(error)


class GoogleSheetsClient:
    """Client for Google Sheets access through a service account."""

    def __init__(self, client: gspread.Client, creds: Credentials | None = None) -> None:
        self._client = client
        self._creds = creds

    @classmethod
    def from_service_account_file(
        cls,
        path: str,
        scopes: list[str] | None = None,
    ) -> GoogleSheetsClient:
        try:
            creds = Credentials.from_service_account_file(path, scopes=scopes or _DEFAULT_SCOPES)
            client = gspread.authorize(creds)
            return cls(client, creds=creds)
        except DefaultCredentialsError as e:
            raise SheetsAuthError(f"Failed to load service account: {e}") from e
        except Exception as e:
            raise SheetsAuthError(f"Auth error: {e}") from e

    @_wrap_api
    def open_by_id(self, spreadsheet_id: str) -> Spreadsheet:
        try:
            gc_sheet = self._client.open_by_key(spreadsheet_id)
            return Spreadsheet(gc_sheet)
        except gspread.SpreadsheetNotFound:
            raise SpreadsheetNotFound(f"Spreadsheet not found: {spreadsheet_id}")


class Spreadsheet:
    """Wrapper for one Google Sheets spreadsheet."""

    def __init__(self, gc_sheet: gspread.Spreadsheet) -> None:
        self._gc = gc_sheet

    @_wrap_api
    def worksheet(self, title: str) -> Worksheet:
        try:
            return Worksheet(self._gc.worksheet(title))
        except gspread.WorksheetNotFound:
            raise WorksheetNotFound(f"Worksheet not found: {title!r}")

    @_wrap_api
    def worksheet_by_index(self, index: int) -> Worksheet:
        try:
            worksheet = self._gc.get_worksheet(index)
            if worksheet is None:
                raise WorksheetNotFound(f"No worksheet at index {index}")
            return Worksheet(worksheet)
        except (TypeError, IndexError) as e:
            raise WorksheetNotFound(f"No worksheet at index {index}: {e}") from e

    @_wrap_api
    def worksheets(self) -> list[Worksheet]:
        return [Worksheet(worksheet) for worksheet in self._gc.worksheets()]


class Worksheet:
    """Wrapper for one worksheet with basic range read/write operations."""

    def __init__(self, worksheet: gspread.Worksheet) -> None:
        self._ws = worksheet

    @_wrap_api
    def get_values(self, a1_range: str | None = None) -> list[list[str]]:
        if a1_range is None:
            return self._ws.get_all_values()
        return self._ws.get(a1_range) or []

    @_wrap_api
    def append_row(
        self,
        values: list[Any],
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        self._ws.append_row(values, value_input_option=value_input_option)

    @_wrap_api
    def append_rows(
        self,
        rows: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        if not rows:
            return
        self._ws.append_rows(rows, value_input_option=value_input_option)

    @_wrap_api
    def update_range(
        self,
        a1_range: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        self._ws.update(a1_range, values, value_input_option=value_input_option)

    @_wrap_api
    def clear_range(self, a1_range: str) -> None:
        self._ws.batch_clear([a1_range])

    @_wrap_api
    def clear_all(self) -> None:
        self._ws.clear()
