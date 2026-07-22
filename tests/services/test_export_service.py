from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.integrations import google_sheets
from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.batch_match_result import BatchMatchResult
from src.models.batch_personalized_offer_result import BatchPersonalizedOfferResult
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import (
    BloggerMatchResult,
    MatchCriteriaScores,
    MatchCriterionScore,
    MatchDecision,
    RegionStatus,
)
from src.models.discovery import DiscoveryCandidate, DiscoveryResult
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.models.personalized_offer import OfferStatus, PersonalizedOffer
from src.services.export_service import (
    DISCOVERED_CANDIDATES_SHEET,
    IDEAL_PROFILE_SHEET,
    MANAGED_SHEETS,
    MATCHING_SHEET,
    OFFERS_SHEET,
    STATS_SHEET,
    TITLE_SHEET,
    ExportService,
    ExportServiceError,
)


def test_export_service_creates_managed_sheets_and_never_modifies_source_sheet(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service_account_file = tmp_path / "service_account.json"
    service_account_file.write_text("{}", encoding="utf-8")
    source_sheet = _worksheet("Референсные блогеры", worksheet_id=1)
    spreadsheet = _spreadsheet([source_sheet])
    fake_client = _fake_client(spreadsheet)
    monkeypatch.setattr(google_sheets.GoogleSheetsClient, "from_service_account_file", fake_client)

    ExportService(
        service_account_file=str(service_account_file),
        spreadsheet_id="spreadsheet-id",
        source_sheet="Референсные блогеры",
    ).export_results(**_export_payload())

    assert source_sheet.cleared is False
    assert source_sheet.updated_ranges == []
    assert [worksheet.title for worksheet in spreadsheet.worksheets()] == [
        "Референсные блогеры",
        *MANAGED_SHEETS,
    ]
    assert spreadsheet.reordered_to_first == TITLE_SHEET


def test_export_service_clears_existing_managed_sheets_without_deleting_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service_account_file = tmp_path / "service_account.json"
    service_account_file.write_text("{}", encoding="utf-8")
    existing_title = _worksheet(TITLE_SHEET, worksheet_id=2)
    existing_stats = _worksheet(STATS_SHEET, worksheet_id=3)
    spreadsheet = _spreadsheet([
        _worksheet("Референсные блогеры", worksheet_id=1),
        existing_title,
        existing_stats,
    ])
    monkeypatch.setattr(google_sheets.GoogleSheetsClient, "from_service_account_file", _fake_client(spreadsheet))

    ExportService(str(service_account_file), "spreadsheet-id", "Референсные блогеры").export_results(**_export_payload())

    assert existing_title.cleared is True
    assert existing_stats.cleared is True
    assert spreadsheet.deleted_titles == []


def test_export_service_writes_russian_statuses_and_human_readable_tables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service_account_file = tmp_path / "service_account.json"
    service_account_file.write_text("{}", encoding="utf-8")
    spreadsheet = _spreadsheet([_worksheet("Референсные блогеры", worksheet_id=1)])
    monkeypatch.setattr(google_sheets.GoogleSheetsClient, "from_service_account_file", _fake_client(spreadsheet))

    ExportService(str(service_account_file), "spreadsheet-id", "Референсные блогеры").export_results(**_export_payload())

    matching_rows = spreadsheet.by_title[MATCHING_SHEET].updated_ranges[0][1]
    offer_rows = spreadsheet.by_title[OFFERS_SHEET].updated_ranges[0][1]
    stats_rows = spreadsheet.by_title[STATS_SHEET].updated_ranges[0][1]
    ideal_rows = spreadsheet.by_title[IDEAL_PROFILE_SHEET].updated_ranges[0][1]

    assert "Решение" in matching_rows[0]
    assert any("Рекомендован" in row for row in matching_rows)
    assert any("Требует проверки" in row for row in matching_rows)
    assert any("Отклонён" in row for row in matching_rows)
    assert any("Готово к отправке" in row for row in offer_rows)
    assert any("Средний балл" in row for row in stats_rows)
    assert any("Ниша" in row for row in ideal_rows)
    assert "{" not in str(ideal_rows)


def test_export_service_formats_each_written_sheet(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service_account_file = tmp_path / "service_account.json"
    service_account_file.write_text("{}", encoding="utf-8")
    spreadsheet = _spreadsheet([_worksheet("Референсные блогеры", worksheet_id=1)])
    monkeypatch.setattr(google_sheets.GoogleSheetsClient, "from_service_account_file", _fake_client(spreadsheet))

    ExportService(str(service_account_file), "spreadsheet-id", "Референсные блогеры").export_results(**_export_payload())

    for title in MANAGED_SHEETS:
        worksheet = spreadsheet.by_title[title]
        assert worksheet.formatted_ranges
        assert worksheet.frozen_rows == [1]
        assert worksheet.resized_columns


def test_export_service_rejects_source_sheet_that_matches_managed_sheet(tmp_path) -> None:
    service_account_file = tmp_path / "service_account.json"
    service_account_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ExportServiceError, match="GOOGLE_SOURCE_SHEET"):
        ExportService(str(service_account_file), "spreadsheet-id", TITLE_SHEET).export_results(**_export_payload())


def _export_payload() -> dict[str, Any]:
    return {
        "run_at": datetime(2026, 7, 23, 10, 30, tzinfo=timezone.utc),
        "reference_profiles_result": ApifyEnrichmentResult(profiles=[_blogger("reference")]),
        "profile_analysis": _ideal_profile_analysis(),
        "discovery_result": _discovery_result(),
        "discovered_profiles_result": ApifyEnrichmentResult(profiles=[_blogger("recommended"), _blogger("review")]),
        "match_result": BatchMatchResult(
            matches=[
                _match_result("recommended", decision=MatchDecision.RECOMMENDED, final_score=90),
                _match_result("review", decision=MatchDecision.REVIEW, final_score=55),
                _match_result("rejected", decision=MatchDecision.REJECTED, final_score=0),
            ],
            errors=[],
            total_candidates=3,
            successful_matches=3,
            failed_matches=0,
        ),
        "personalized_offer_result": BatchPersonalizedOfferResult(
            offers=[
                _offer("recommended", decision=MatchDecision.RECOMMENDED, status=OfferStatus.READY, score=90),
                _offer("review", decision=MatchDecision.REVIEW, status=OfferStatus.NEEDS_REVIEW, score=55),
            ],
            errors=[],
            total_matches=3,
            eligible_candidates=2,
            skipped_rejected=1,
            successful_offers=2,
            failed_offers=0,
        ),
    }


def _blogger(username: str) -> BloggerProfile:
    return BloggerProfile(
        input_url=f"https://www.instagram.com/{username}/",
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        biography="Short bio",
        followers_count=1000,
        raw_data={"username": username},
    )


def _ideal_profile_analysis() -> IdealProfileAnalysis:
    return IdealProfileAnalysis(
        ideal_profile=IdealBloggerProfile(
            niche="семейный лайфстайл",
            min_followers=1000,
            max_followers=50000,
            required_topics=["семья", "дом"],
            required_brand_style="естественная подача",
        ),
        source_profiles_count=1,
        common_traits=["Живой тон"],
        important_selection_criteria=["Релевантная тематика"],
        observed_variations=["Разный размер аудитории"],
        data_limitations=["Мало данных"],
        explanation="Профиль построен по референсам.",
        confidence=60.0,
    )


def _discovery_result() -> DiscoveryResult:
    return DiscoveryResult(
        queries=["site:instagram.com семейный блогер"],
        candidates=[
            DiscoveryCandidate(
                username="recommended",
                profile_url="https://www.instagram.com/recommended/",
                source_query="site:instagram.com семейный блогер",
                title="Recommended Creator",
                description="Описание",
            ),
            DiscoveryCandidate(
                username="review",
                profile_url="https://www.instagram.com/review/",
                source_query="site:instagram.com семейный блогер",
            ),
        ],
        total_candidates=2,
    )


def _match_result(username: str, *, decision: MatchDecision, final_score: int) -> BloggerMatchResult:
    region_status = RegionStatus.TARGET
    detected_region: str | None = "Россия"
    rejection_reasons: list[str] = []
    risks: list[str] = []
    if decision == MatchDecision.REVIEW:
        region_status = RegionStatus.UNKNOWN
        detected_region = None
        risks = ["Проверить регион."]
    if decision == MatchDecision.REJECTED:
        region_status = RegionStatus.NON_TARGET
        detected_region = "Украина"
        rejection_reasons = ["Не целевой регион."]

    return BloggerMatchResult(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        final_score=final_score,
        decision=decision,
        region_status=region_status,
        region_confidence=80,
        detected_region=detected_region,
        strengths=["Тематика совпадает."],
        risks=risks,
        rejection_reasons=rejection_reasons,
        match_summary="Кандидат подходит.",
        criteria_scores=_criteria_scores(),
    )


def _offer(username: str, *, decision: MatchDecision, status: OfferStatus, score: int) -> PersonalizedOffer:
    return PersonalizedOffer(
        profile_url=f"https://www.instagram.com/{username}/",
        username=username,
        match_decision=decision,
        match_score=score,
        offer_status=status,
        personalization_points=["Семейная тематика профиля."],
        collaboration_angle="Подходит для бартерного сотрудничества.",
        proposed_format="Короткий обзор продукта.",
        subject="Возможное сотрудничество",
        message="Здравствуйте! Хотели бы предложить сотрудничество с предоставлением продукта.",
        manual_review_notes=["Проверить возможность бартера."] if status == OfferStatus.NEEDS_REVIEW else [],
    )


def _criteria_scores() -> MatchCriteriaScores:
    return MatchCriteriaScores(
        thematic_fit=_criterion(),
        audience_fit=_criterion(),
        geography_fit=_criterion(),
        language_fit=_criterion(),
        account_size_fit=_criterion(),
        engagement_fit=_criterion(),
        content_style_fit=_criterion(),
        commercial_fit=_criterion(),
    )


def _criterion() -> MatchCriterionScore:
    return MatchCriterionScore(score=80, confidence=70, reason="Тестовая причина.")


def _worksheet(title: str, worksheet_id: int):
    class FakeWorksheet:
        def __init__(self) -> None:
            self.title = title
            self.id = worksheet_id
            self.cleared = False
            self.updated_ranges: list[tuple[str, list[list[Any]]]] = []
            self.formatted_ranges: list[tuple[str, dict[str, Any]]] = []
            self.frozen_rows: list[int] = []
            self.resized_columns: list[tuple[int, int]] = []

        def clear_all(self) -> None:
            self.cleared = True

        def update_range(self, a1_range: str, values: list[list[Any]], value_input_option: str = "USER_ENTERED") -> None:
            self.updated_ranges.append((a1_range, values))

        def format_range(self, a1_range: str, cell_format: dict[str, Any]) -> None:
            self.formatted_ranges.append((a1_range, cell_format))

        def freeze_rows(self, rows: int) -> None:
            self.frozen_rows.append(rows)

        def auto_resize_columns(self, start_index: int, end_index: int) -> None:
            self.resized_columns.append((start_index, end_index))

    return FakeWorksheet()


def _spreadsheet(initial_worksheets: list[Any]):
    class FakeSpreadsheet:
        def __init__(self) -> None:
            self._worksheets = list(initial_worksheets)
            self.by_title = {worksheet.title: worksheet for worksheet in self._worksheets}
            self.deleted_titles: list[str] = []
            self.reordered_to_first: str | None = None

        def worksheets(self) -> list[Any]:
            return list(self._worksheets)

        def add_worksheet(self, title: str, rows: int = 100, cols: int = 20) -> Any:
            worksheet = _worksheet(title, worksheet_id=len(self._worksheets) + 10)
            self._worksheets.append(worksheet)
            self.by_title[title] = worksheet
            return worksheet

        def reorder_worksheet(self, worksheet: Any, index: int) -> None:
            self.reordered_to_first = worksheet.title

    return FakeSpreadsheet()


def _fake_client(spreadsheet: Any):
    class FakeClient:
        def open_by_id(self, spreadsheet_id: str) -> Any:
            return spreadsheet

    return lambda path: FakeClient()
