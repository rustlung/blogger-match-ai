import sys
from datetime import datetime
from pathlib import Path

from src.config import settings
from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.blogger import BloggerProfile
from src.models.discovery import DiscoveryResult
from src.models.failed_profile import FailedProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.services.apify_service import ApifyService, ApifyServiceError
from src.services.brave_search_client import BraveSearchClient
from src.services.discovery_query_builder import DiscoveryQueryBuilder
from src.services.discovery_service import DiscoveryService, DiscoveryServiceError, reference_usernames_from_urls
from src.services.ideal_profile_prompt_builder import IdealProfilePromptBuilder
from src.services.ideal_profile_service import IdealProfileService, IdealProfileServiceError
from src.services.sheets_service import SheetsService, SheetsServiceError
from src.utils.json_writer import AtomicJsonWriteError, atomic_write_json
from src.utils.logger import logger


ANALYSIS_RESULTS_PATH = Path("results/analysis_results.json")
IDEAL_PROFILE_RESULTS_PATH = Path("results/ideal_blogger_profile.json")
DISCOVERED_CANDIDATES_PATH = Path("results/discovered_candidates.json")
MIN_RECOMMENDED_REFERENCE_PROFILES = 3


class AnalysisResultsSaveError(RuntimeError):
    pass


class IdealProfileResultsSaveError(RuntimeError):
    pass


class DiscoveryResultsSaveError(RuntimeError):
    pass


def main() -> int:
    _configure_console_output()
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
    print(f"Found unique reference Instagram profiles: {len(urls)}")

    if settings.APIFY_SOURCE_PROFILES_LIMIT <= 0:
        print("Ошибка: APIFY_SOURCE_PROFILES_LIMIT должен быть больше 0.")
        return 1

    limited_urls = urls[: settings.APIFY_SOURCE_PROFILES_LIMIT]
    print(f"Reference profiles requested: {len(limited_urls)}")

    apify_service = ApifyService(
        api_token=settings.APIFY_API_TOKEN,
        actor_id=settings.APIFY_ACTOR_ID,
        timeout_seconds=settings.APIFY_REQUEST_TIMEOUT_SECONDS,
    )

    try:
        enrichment_result = apify_service.enrich_profiles(limited_urls)
    except ApifyServiceError as e:
        print(f"Ошибка: {e}")
        return 1

    print(f"Reference profiles parsed: {len(enrichment_result.profiles)}")
    print(f"Apify failures: {len(enrichment_result.failed_profiles)}")

    if enrichment_result.failed_profiles:
        print()
        print("Failed profiles:")
        for failed_profile in enrichment_result.failed_profiles:
            print(_failed_profile_line(failed_profile))

    if not enrichment_result.profiles:
        print()
        print("Ошибка: нет успешных эталонных профилей для построения портрета.")
        return 1

    llm_config_error = _validate_llm_configuration()
    if llm_config_error is not None:
        print(f"LLM configuration error: {llm_config_error}")
        return 1

    if len(enrichment_result.profiles) < MIN_RECOMMENDED_REFERENCE_PROFILES:
        print(
            "Warning: reference sample is small; "
            f"recommended at least {MIN_RECOMMENDED_REFERENCE_PROFILES} profiles."
        )

    print(f"Building ideal blogger profile from {len(enrichment_result.profiles)} profiles...")

    ideal_profile_service = IdealProfileService(
        prompt_builder=IdealProfilePromptBuilder(),
        api_key=settings.openai_api_key or "",
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        timeout=settings.openai_request_timeout_seconds,
    )

    try:
        profile_analysis = ideal_profile_service.build_ideal_profile(enrichment_result.profiles)
    except IdealProfileServiceError as e:
        print(f"Ошибка: {e}")
        return 1

    print("Ideal blogger profile created.")
    print(f"Confidence: {profile_analysis.confidence}")
    print(f"Niche: {_display(profile_analysis.ideal_profile.niche)}")
    print(
        "Followers: "
        f"{_followers_range(profile_analysis.ideal_profile.min_followers, profile_analysis.ideal_profile.max_followers)}"
    )
    _print_key_selection_criteria(profile_analysis)

    summary = _ideal_profile_summary_payload(
        profiles_requested=len(limited_urls),
        profiles_analyzed=len(enrichment_result.profiles),
        apify_failures=len(enrichment_result.failed_profiles),
    )

    if len(enrichment_result.profiles) < MIN_RECOMMENDED_REFERENCE_PROFILES:
        _ensure_small_sample_limitation(profile_analysis, len(enrichment_result.profiles))

    if not _save_ideal_profile_or_report_error(
        profile_analysis=profile_analysis,
        apify_failures=enrichment_result.failed_profiles,
        summary=summary,
    ):
        return 1

    discovery_config_error = _validate_discovery_configuration()
    if discovery_config_error is not None:
        print(f"Discovery configuration error: {discovery_config_error}")
        return 1

    reference_usernames = _reference_usernames(
        reference_urls=limited_urls,
        reference_profiles=enrichment_result.profiles,
    )
    discovery_service = DiscoveryService(
        query_builder=DiscoveryQueryBuilder(),
        search_client=BraveSearchClient(api_key=settings.BRAVE_SEARCH_API_KEY),
    )

    try:
        discovery_result = discovery_service.discover(
            ideal_profile=profile_analysis.ideal_profile,
            reference_usernames=reference_usernames,
        )
    except DiscoveryServiceError as e:
        print(f"Ошибка: {e}")
        return 1

    if not _save_discovery_results_or_report_error(discovery_result):
        return 1

    print(f"Discovery search queries: {len(discovery_result.queries)}")
    print(f"Discovered unique candidates: {discovery_result.total_candidates}")
    print("Discovered candidates saved to results/discovered_candidates.json")

    return 0


def build_ideal_blogger_profile() -> IdealBloggerProfile:
    return IdealBloggerProfile(
        niche="general lifestyle",
        target_gender=None,
        target_age_range=None,
        min_followers=None,
        max_followers=None,
        required_topics=[],
        excluded_topics=[],
        preferred_regions=[],
        preferred_languages=[],
        required_brand_style="authentic, brand-safe, non-controversial content",
    )


def _validate_llm_configuration() -> str | None:
    if not settings.openai_api_key:
        return "OPENAI_API_KEY is not configured."

    if not settings.openai_base_url:
        return "OPENAI_BASE_URL is not configured."

    if not settings.openai_model:
        return "OPENAI_MODEL is not configured."

    if settings.openai_request_timeout_seconds <= 0:
        return "OPENAI_REQUEST_TIMEOUT_SECONDS must be greater than 0."

    return None


def _validate_discovery_configuration() -> str | None:
    if not settings.BRAVE_SEARCH_API_KEY:
        return "BRAVE_SEARCH_API_KEY не задан."

    return None


def _print_analyzed_candidate(candidate: AnalyzedCandidate) -> None:
    analysis = candidate.analysis

    print()
    print(f"Candidate: {candidate.blogger.username}")
    print(f"Overall score: {analysis.overall_score}")
    print(f"Recommendation: {analysis.recommendation}")
    print(f"Confidence: {analysis.confidence}")

    print()
    print("Strengths:")
    if analysis.strengths:
        for strength in analysis.strengths:
            print(f"- {strength}")
    else:
        print("- Not specified")

    print()
    print("Weaknesses:")
    if analysis.weaknesses:
        for weakness in analysis.weaknesses:
            print(f"- {weakness}")
    else:
        print("- Not specified")


def save_analysis_results(
    *,
    analyzed_candidates: list[AnalyzedCandidate],
    apify_failures: list[FailedProfile],
    analysis_failures: list[tuple[BloggerProfile, str]],
    summary: dict[str, int],
    output_path: Path = ANALYSIS_RESULTS_PATH,
) -> None:
    payload = {
        "generated_at": _generated_at(),
        "summary": summary,
        "analyzed_candidates": [_analyzed_candidate_payload(candidate) for candidate in analyzed_candidates],
        "apify_failures": [failed_profile.model_dump(mode="json") for failed_profile in apify_failures],
        "llm_failures": [_llm_failure_payload(blogger, error) for blogger, error in analysis_failures],
    }

    try:
        atomic_write_json(payload, output_path)
    except AtomicJsonWriteError as exc:
        raise AnalysisResultsSaveError("Не удалось сохранить результаты анализа.") from exc


def save_ideal_profile_results(
    *,
    profile_analysis: IdealProfileAnalysis,
    apify_failures: list[FailedProfile],
    summary: dict[str, int],
    output_path: Path = IDEAL_PROFILE_RESULTS_PATH,
) -> None:
    payload = {
        "generated_at": _generated_at(),
        "summary": summary,
        "profile_analysis": profile_analysis.model_dump(mode="json"),
        "apify_failures": [failed_profile.model_dump(mode="json") for failed_profile in apify_failures],
    }

    try:
        atomic_write_json(payload, output_path)
    except AtomicJsonWriteError as exc:
        raise IdealProfileResultsSaveError("Не удалось сохранить портрет идеального блогера.") from exc


def save_discovery_results(
    discovery_result: DiscoveryResult,
    output_path: Path = DISCOVERED_CANDIDATES_PATH,
) -> None:
    try:
        atomic_write_json(discovery_result.model_dump(mode="json"), output_path)
    except AtomicJsonWriteError as exc:
        raise DiscoveryResultsSaveError("Не удалось сохранить найденных кандидатов.") from exc


def _save_results_or_report_error(
    *,
    analyzed_candidates: list[AnalyzedCandidate],
    apify_failures: list[FailedProfile],
    analysis_failures: list[tuple[BloggerProfile, str]],
    summary: dict[str, int],
) -> bool:
    try:
        save_analysis_results(
            analyzed_candidates=analyzed_candidates,
            apify_failures=apify_failures,
            analysis_failures=analysis_failures,
            summary=summary,
        )
    except AnalysisResultsSaveError as e:
        logger.error("Analysis results save failed: error_type=%s", type(e.__cause__).__name__)
        print(f"Ошибка: {e}")
        return False

    print("Analysis results saved to results/analysis_results.json")
    return True


def _save_ideal_profile_or_report_error(
    *,
    profile_analysis: IdealProfileAnalysis,
    apify_failures: list[FailedProfile],
    summary: dict[str, int],
) -> bool:
    try:
        save_ideal_profile_results(
            profile_analysis=profile_analysis,
            apify_failures=apify_failures,
            summary=summary,
        )
    except IdealProfileResultsSaveError as e:
        logger.error("Ideal profile results save failed: error_type=%s", type(e.__cause__).__name__)
        print(f"Ошибка: {e}")
        return False

    print("Ideal blogger profile saved to results/ideal_blogger_profile.json")
    return True


def _save_discovery_results_or_report_error(discovery_result: DiscoveryResult) -> bool:
    try:
        save_discovery_results(discovery_result)
    except DiscoveryResultsSaveError as e:
        logger.error("Discovery results save failed: error_type=%s", type(e.__cause__).__name__)
        print(f"Ошибка: {e}")
        return False

    return True


def _analysis_summary_payload(
    *,
    profiles_received_from_apify: int,
    apify_failures: int,
    sent_to_llm: int,
    analyzed_successfully: int,
    llm_failures: int,
) -> dict[str, int]:
    return {
        "profiles_received_from_apify": profiles_received_from_apify,
        "apify_failures": apify_failures,
        "sent_to_llm": sent_to_llm,
        "analyzed_successfully": analyzed_successfully,
        "llm_failures": llm_failures,
    }


def _ideal_profile_summary_payload(
    *,
    profiles_requested: int,
    profiles_analyzed: int,
    apify_failures: int,
) -> dict[str, int]:
    return {
        "profiles_requested": profiles_requested,
        "profiles_analyzed": profiles_analyzed,
        "apify_failures": apify_failures,
    }


def _analyzed_candidate_payload(candidate: AnalyzedCandidate) -> dict[str, object]:
    blogger_payload = candidate.blogger.model_dump(mode="json", exclude={"raw_data"})
    return {
        "blogger": blogger_payload,
        "analysis": candidate.analysis.model_dump(mode="json"),
    }


def _llm_failure_payload(blogger: BloggerProfile, error_message: str) -> dict[str, str | None]:
    return {
        "username": blogger.username or None,
        "profile_url": blogger.profile_url or blogger.input_url,
        "error": error_message,
    }


def _reference_usernames(reference_urls: list[str], reference_profiles: list[BloggerProfile]) -> set[str]:
    usernames = reference_usernames_from_urls(reference_urls)
    for profile in reference_profiles:
        if profile.username:
            usernames.add(profile.username.casefold())
    return usernames


def _generated_at() -> str:
    return datetime.now().astimezone().isoformat()


def _ensure_small_sample_limitation(profile_analysis: IdealProfileAnalysis, profiles_count: int) -> None:
    limitation = (
        f"Выборка содержит только {profiles_count} профиль; "
        f"для более надежного портрета рекомендуется минимум {MIN_RECOMMENDED_REFERENCE_PROFILES} профиля."
    )
    if limitation not in profile_analysis.data_limitations:
        profile_analysis.data_limitations.append(limitation)


def _print_key_selection_criteria(profile_analysis: IdealProfileAnalysis) -> None:
    criteria = profile_analysis.important_selection_criteria[:5]
    if not criteria:
        return

    print("Key selection criteria:")
    for criterion in criteria:
        print(f"- {criterion}")


def _print_analysis_summary(
    *,
    summary: dict[str, int],
    analysis_failures: list[tuple[BloggerProfile, str]],
) -> None:
    print()
    print("Analysis summary")
    print(f"Profiles received from Apify: {summary['profiles_received_from_apify']}")
    print(f"Apify failures: {summary['apify_failures']}")
    print(f"Sent to LLM: {summary['sent_to_llm']}")
    print(f"Analyzed successfully: {summary['analyzed_successfully']}")
    print(f"LLM failures: {summary['llm_failures']}")

    if analysis_failures:
        print()
        print("LLM analysis failures:")
        for blogger, error_message in analysis_failures:
            print(f"- {_blogger_identifier(blogger)} — {error_message}")


def _display(value: object) -> object:
    if value is None or value == "":
        return "-"
    return value


def _followers_range(min_followers: int | None, max_followers: int | None) -> str:
    if min_followers is None and max_followers is None:
        return "-"
    if min_followers is not None and max_followers is not None:
        return f"{min_followers} - {max_followers}"
    if min_followers is not None:
        return f"From {min_followers}"
    return f"Up to {max_followers}"


def _failed_profile_line(failed_profile: FailedProfile) -> str:
    name = failed_profile.username or failed_profile.input_url or "-"
    description = f": {failed_profile.error_description}" if failed_profile.error_description else ""
    return f"- {name} — {failed_profile.error_code}{description}"


def _blogger_identifier(blogger: BloggerProfile) -> str:
    return blogger.username or blogger.profile_url or blogger.input_url or "-"


def _configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
