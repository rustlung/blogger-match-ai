from src.config import settings
from src.services.sheets_service import SheetsService, SheetsServiceError
from src.utils.logger import logger


def main() -> int:
    _ = logger

    print("=================================")
    print(" Blogger Match AI")
    print("=================================")
    print()

    service = SheetsService(
        service_account_file=settings.GOOGLE_SERVICE_ACCOUNT_FILE,
        spreadsheet_id=settings.GOOGLE_SPREADSHEET_ID,
        source_sheet=settings.GOOGLE_SOURCE_SHEET,
        source_column=settings.GOOGLE_SOURCE_COLUMN,
    )

    try:
        urls = service.get_instagram_urls()
    except SheetsServiceError as e:
        print(f"Ошибка: {e}")
        return 1

    print("Google Sheets read successfully.")
    print(f"Found unique Instagram profiles: {len(urls)}")
    for index, url in enumerate(urls, start=1):
        print(f"{index}. {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
