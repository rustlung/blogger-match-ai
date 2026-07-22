from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.batch_match_result import BatchMatchResult
from src.models.batch_personalized_offer_result import BatchPersonalizedOfferResult
from src.models.blogger_match_result import BloggerMatchResult, MatchDecision
from src.models.discovery import DiscoveryResult
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.models.personalized_offer import OfferStatus
from src.utils.logger import logger


TITLE_SHEET = "Титульный лист"
IDEAL_PROFILE_SHEET = "Идеальный профиль"
DISCOVERED_CANDIDATES_SHEET = "Найденные кандидаты"
MATCHING_SHEET = "Сопоставление"
OFFERS_SHEET = "Предложения"
STATS_SHEET = "Статистика"

MANAGED_SHEETS = [
    TITLE_SHEET,
    IDEAL_PROFILE_SHEET,
    DISCOVERED_CANDIDATES_SHEET,
    MATCHING_SHEET,
    OFFERS_SHEET,
    STATS_SHEET,
]


class ExportServiceError(RuntimeError):
    pass


class ExportService:
    def __init__(
        self,
        service_account_file: str,
        spreadsheet_id: str,
        source_sheet: str,
    ) -> None:
        self.service_account_file = service_account_file
        self.spreadsheet_id = spreadsheet_id
        self.source_sheet = source_sheet

    def export_results(
        self,
        *,
        run_at: datetime,
        reference_profiles_result: ApifyEnrichmentResult,
        profile_analysis: IdealProfileAnalysis,
        discovery_result: DiscoveryResult,
        discovered_profiles_result: ApifyEnrichmentResult,
        match_result: BatchMatchResult,
        personalized_offer_result: BatchPersonalizedOfferResult,
    ) -> None:
        self._validate_settings()

        try:
            from src.integrations.google_sheets import GoogleSheetsClient, SheetsError, WorksheetNotFound

            client = GoogleSheetsClient.from_service_account_file(self.service_account_file)
            spreadsheet = client.open_by_id(self.spreadsheet_id)

            source_title = self.source_sheet
            worksheets = {
                worksheet.title: worksheet
                for worksheet in spreadsheet.worksheets()
            }

            managed_worksheets = {}
            for title in MANAGED_SHEETS:
                if title in worksheets:
                    worksheet = worksheets[title]
                    if title != source_title:
                        worksheet.clear_all()
                else:
                    worksheet = spreadsheet.add_worksheet(title=title, rows=100, cols=20)
                managed_worksheets[title] = worksheet

            spreadsheet.reorder_worksheet(managed_worksheets[TITLE_SHEET], 0)

            _write_table(
                managed_worksheets[TITLE_SHEET],
                _title_rows(
                    run_at=run_at,
                    source_sheet=source_title,
                    reference_profiles_result=reference_profiles_result,
                    discovery_result=discovery_result,
                    match_result=match_result,
                    personalized_offer_result=personalized_offer_result,
                ),
            )
            _write_table(managed_worksheets[IDEAL_PROFILE_SHEET], _ideal_profile_rows(profile_analysis))
            _write_table(
                managed_worksheets[DISCOVERED_CANDIDATES_SHEET],
                _discovered_candidates_rows(discovery_result, discovered_profiles_result),
            )
            _write_table(managed_worksheets[MATCHING_SHEET], _match_rows(match_result))
            _write_table(managed_worksheets[OFFERS_SHEET], _offer_rows(personalized_offer_result))
            _write_table(
                managed_worksheets[STATS_SHEET],
                _stats_rows(
                    reference_profiles_result=reference_profiles_result,
                    discovery_result=discovery_result,
                    match_result=match_result,
                    personalized_offer_result=personalized_offer_result,
                ),
            )
        except ImportError as exc:
            raise ExportServiceError("Не установлены зависимости для экспорта в Google Sheets.") from exc
        except WorksheetNotFound as exc:
            raise ExportServiceError(f"Не найден лист Google Sheets: {exc}") from exc
        except SheetsError as exc:
            raise ExportServiceError(f"Не удалось экспортировать результаты в Google Sheets: {exc}") from exc

        logger.info("Google Sheets export completed: spreadsheet_id=%s", self.spreadsheet_id)

    def _validate_settings(self) -> None:
        if _has_service_account_json():
            pass
        elif not self.service_account_file:
            raise ExportServiceError("Не задан GOOGLE_SERVICE_ACCOUNT_FILE.")
        elif not Path(self.service_account_file).is_file():
            raise ExportServiceError("Файл service account не найден.")

        if not self.spreadsheet_id:
            raise ExportServiceError("Не задан GOOGLE_SPREADSHEET_ID.")

        if not self.source_sheet:
            raise ExportServiceError("Не задан GOOGLE_SOURCE_SHEET.")

        if self.source_sheet in MANAGED_SHEETS:
            raise ExportServiceError("GOOGLE_SOURCE_SHEET не должен совпадать с автоматически обновляемыми листами.")


def _write_table(worksheet: Any, rows: list[list[Any]]) -> None:
    worksheet.update_range("A1", rows)
    _format_worksheet(worksheet, rows)


def _format_worksheet(worksheet: Any, rows: list[list[Any]]) -> None:
    if not rows:
        return
    try:
        worksheet.format_range("1:1", {"textFormat": {"bold": True}})
        worksheet.freeze_rows(1)
        worksheet.auto_resize_columns(0, max(len(row) for row in rows))
    except Exception as exc:
        logger.warning("Google Sheets formatting skipped: error_type=%s", type(exc).__name__)


def _title_rows(
    *,
    run_at: datetime,
    source_sheet: str,
    reference_profiles_result: ApifyEnrichmentResult,
    discovery_result: DiscoveryResult,
    match_result: BatchMatchResult,
    personalized_offer_result: BatchPersonalizedOfferResult,
) -> list[list[Any]]:
    decision_counts = _decision_counts(match_result)
    return [
        ["Параметр", "Значение"],
        ["Название проекта", "Blogger Match AI"],
        ["Дата и время запуска", run_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %z")],
        ["Референсных блогеров", len(reference_profiles_result.profiles)],
        ["Найденных кандидатов", discovery_result.total_candidates],
        ["Проанализированных", match_result.successful_matches],
        ["Рекомендованных", decision_counts[MatchDecision.RECOMMENDED]],
        ["Требующих проверки", decision_counts[MatchDecision.REVIEW]],
        ["Отклонённых", decision_counts[MatchDecision.REJECTED]],
        ["Сформированных предложений", personalized_offer_result.successful_offers],
        [
            "Описание",
            (
                f"Лист «{source_sheet}» является источником данных и не изменяется программой. "
                "Остальные листы автоматически обновляются при каждом запуске."
            ),
        ],
    ]


def _ideal_profile_rows(profile_analysis: IdealProfileAnalysis) -> list[list[Any]]:
    profile = profile_analysis.ideal_profile
    rows = [
        ["Параметр", "Значение"],
        ["Ниша", profile.niche],
        ["Целевой пол", _display(profile.target_gender)],
        ["Целевой возраст", _display(profile.target_age_range)],
        ["Минимум подписчиков", _display(profile.min_followers)],
        ["Максимум подписчиков", _display(profile.max_followers)],
        ["Обязательные темы", _join(profile.required_topics)],
        ["Исключённые темы", _join(profile.excluded_topics)],
        ["Предпочтительные регионы", _join(profile.preferred_regions)],
        ["Предпочтительные языки", _join(profile.preferred_languages)],
        ["Стиль бренда", _display(profile.required_brand_style)],
        ["Количество референсов в анализе", profile_analysis.source_profiles_count],
        ["Уверенность", profile_analysis.confidence],
        ["Общие черты", _join(profile_analysis.common_traits)],
        ["Ключевые критерии отбора", _join(profile_analysis.important_selection_criteria)],
        ["Наблюдаемые вариации", _join(profile_analysis.observed_variations)],
        ["Ограничения данных", _join(profile_analysis.data_limitations)],
        ["Объяснение", profile_analysis.explanation],
    ]
    return rows


def _discovered_candidates_rows(
    discovery_result: DiscoveryResult,
    discovered_profiles_result: ApifyEnrichmentResult,
) -> list[list[Any]]:
    profile_by_url = {
        profile.profile_url.rstrip("/").casefold(): profile
        for profile in discovered_profiles_result.profiles
    }
    rows = [["Ссылка", "Ник", "Название из поиска", "Описание из поиска", "Источник запроса", "Подписчики"]]
    for candidate in discovery_result.candidates:
        profile = profile_by_url.get(candidate.profile_url.rstrip("/").casefold())
        rows.append(
            [
                candidate.profile_url,
                candidate.username,
                _display(candidate.title),
                _display(candidate.description),
                candidate.source_query,
                _display(profile.followers_count if profile else None),
            ]
        )
    return rows


def _match_rows(match_result: BatchMatchResult) -> list[list[Any]]:
    rows = [["Ссылка", "Ник", "Итоговый балл", "Решение", "Основные причины", "Риски", "Объяснение Matcher"]]
    for match in match_result.matches:
        rows.append(
            [
                match.profile_url,
                match.username,
                match.final_score,
                _localized_decision(match.decision),
                _join(match.strengths or match.rejection_reasons),
                _join(match.risks),
                match.match_summary,
            ]
        )
    return rows


def _offer_rows(personalized_offer_result: BatchPersonalizedOfferResult) -> list[list[Any]]:
    rows = [["Ник", "Решение", "Статус", "Тема письма", "Текст предложения", "Заметки для ручной проверки"]]
    for offer in personalized_offer_result.offers:
        rows.append(
            [
                offer.username,
                _localized_decision(offer.match_decision),
                _localized_offer_status(offer.offer_status),
                offer.subject,
                offer.message,
                _join(offer.manual_review_notes),
            ]
        )
    return rows


def _stats_rows(
    *,
    reference_profiles_result: ApifyEnrichmentResult,
    discovery_result: DiscoveryResult,
    match_result: BatchMatchResult,
    personalized_offer_result: BatchPersonalizedOfferResult,
) -> list[list[Any]]:
    decision_counts = _decision_counts(match_result)
    scores = [match.final_score for match in match_result.matches]
    return [
        ["Метрика", "Значение"],
        ["Количество референсов", len(reference_profiles_result.profiles)],
        ["Найдено кандидатов", discovery_result.total_candidates],
        ["Проанализировано", match_result.successful_matches],
        ["Рекомендовано", decision_counts[MatchDecision.RECOMMENDED]],
        ["Требует проверки", decision_counts[MatchDecision.REVIEW]],
        ["Отклонено", decision_counts[MatchDecision.REJECTED]],
        ["Сформировано предложений", personalized_offer_result.successful_offers],
        ["Средний балл", round(mean(scores), 2) if scores else "-"],
    ]


def _decision_counts(match_result: BatchMatchResult) -> dict[MatchDecision, int]:
    counts = {
        MatchDecision.RECOMMENDED: 0,
        MatchDecision.REVIEW: 0,
        MatchDecision.REJECTED: 0,
    }
    for match in match_result.matches:
        counts[match.decision] += 1
    return counts


def _localized_decision(decision: MatchDecision) -> str:
    return {
        MatchDecision.RECOMMENDED: "Рекомендован",
        MatchDecision.REVIEW: "Требует проверки",
        MatchDecision.REJECTED: "Отклонён",
    }[decision]


def _localized_offer_status(status: OfferStatus) -> str:
    return {
        OfferStatus.READY: "Готово к отправке",
        OfferStatus.NEEDS_REVIEW: "Требует проверки",
    }[status]


def _display(value: object) -> object:
    if value is None or value == "":
        return "-"
    return value


def _join(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return "-"
    return "\n".join(cleaned)


def _has_service_account_json() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip())
