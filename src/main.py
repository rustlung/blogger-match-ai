import sys

from src.config import settings
from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.blogger import BloggerProfile
from src.models.failed_profile import FailedProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.apify_service import ApifyService, ApifyServiceError
from src.services.llm_service import LLMService, LLMServiceError
from src.services.matcher_service import MatcherService
from src.services.prompt_builder import PromptBuilder
from src.services.sheets_service import SheetsService, SheetsServiceError
from src.utils.logger import logger


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
    print(f"Found unique Instagram profiles: {len(urls)}")

    if settings.APIFY_SOURCE_PROFILES_LIMIT <= 0:
        print("Ошибка: APIFY_SOURCE_PROFILES_LIMIT должен быть больше 0.")
        return 1

    limited_urls = urls[: settings.APIFY_SOURCE_PROFILES_LIMIT]
    print(f"Sending profiles to Apify: {len(limited_urls)}")

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

    print(f"Total profiles: {len(enrichment_result.profiles) + len(enrichment_result.failed_profiles)}")
    print(f"Parsed successfully: {len(enrichment_result.profiles)}")
    print(f"Failed: {len(enrichment_result.failed_profiles)}")

    if enrichment_result.failed_profiles:
        print()
        print("Failed profiles:")
        for failed_profile in enrichment_result.failed_profiles:
            print(_failed_profile_line(failed_profile))

    if not enrichment_result.profiles:
        print()
        print("No successful Apify profiles available for AI analysis.")
        _print_analysis_summary(
            profiles_received=len(enrichment_result.profiles),
            apify_failures=len(enrichment_result.failed_profiles),
            sent_to_llm=0,
            analyzed_candidates=[],
            analysis_failures=[],
        )
        return 0

    llm_config_error = _validate_llm_configuration()
    if llm_config_error is not None:
        print(f"LLM configuration error: {llm_config_error}")
        return 1

    ideal_profile = build_ideal_blogger_profile()
    prompt_builder = PromptBuilder()
    llm_service = LLMService(
        api_key=settings.openai_api_key or "",
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        timeout=settings.openai_request_timeout_seconds,
    )
    matcher_service = MatcherService(
        prompt_builder=prompt_builder,
        llm_service=llm_service,
    )

    analyzed_candidates: list[AnalyzedCandidate] = []
    analysis_failures: list[tuple[BloggerProfile, str]] = []

    for blogger in enrichment_result.profiles:
        try:
            analyzed_candidate = matcher_service.match_candidate(
                ideal_profile=ideal_profile,
                blogger=blogger,
            )
        except LLMServiceError as e:
            analysis_failures.append((blogger, str(e)))
            continue

        analyzed_candidates.append(analyzed_candidate)
        _print_analyzed_candidate(analyzed_candidate)

    _print_analysis_summary(
        profiles_received=len(enrichment_result.profiles),
        apify_failures=len(enrichment_result.failed_profiles),
        sent_to_llm=len(enrichment_result.profiles),
        analyzed_candidates=analyzed_candidates,
        analysis_failures=analysis_failures,
    )

    if not analyzed_candidates and analysis_failures:
        return 1

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


def _print_analysis_summary(
    profiles_received: int,
    apify_failures: int,
    sent_to_llm: int,
    analyzed_candidates: list[AnalyzedCandidate],
    analysis_failures: list[tuple[BloggerProfile, str]],
) -> None:
    print()
    print("Analysis summary")
    print(f"Profiles received from Apify: {profiles_received}")
    print(f"Apify failures: {apify_failures}")
    print(f"Sent to LLM: {sent_to_llm}")
    print(f"Analyzed successfully: {len(analyzed_candidates)}")
    print(f"LLM failures: {len(analysis_failures)}")

    if analysis_failures:
        print()
        print("LLM analysis failures:")
        for blogger, error_message in analysis_failures:
            print(f"- {_blogger_identifier(blogger)} — {error_message}")


def _display(value: object) -> object:
    if value is None or value == "":
        return "-"
    return value


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
