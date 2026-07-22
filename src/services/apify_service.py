from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.blogger import BloggerProfile
from src.models.failed_profile import FailedProfile
from src.services.sheets_service import normalize_instagram_profile_url
from src.utils.logger import logger


class ApifyServiceError(Exception):
    pass


_NON_RETRYABLE_PROFILE_ERRORS = {
    "not_found",
    "invalid_url",
    "profile_not_found",
    "private_profile",
}

_RETRYABLE_PROFILE_ERRORS = {
    "timeout",
    "rate_limit",
    "temporarily_unavailable",
    "instagram_error",
    "internal_error",
}


def parse_apify_profile(item: dict[str, Any]) -> BloggerProfile | None:
    username = _first_text(item, ("username", "ownerUsername"))
    input_url = _first_text(item, ("inputUrl", "input_url"))
    raw_profile_url = _first_text(item, ("url", "profileUrl", "inputUrl"))

    if username is None and raw_profile_url is not None:
        normalized_from_url = normalize_instagram_profile_url(raw_profile_url)
        username = _username_from_profile_url(normalized_from_url)

    if username is not None:
        profile_url = normalize_instagram_profile_url(username)
    elif raw_profile_url is not None:
        profile_url = normalize_instagram_profile_url(raw_profile_url)
        username = _username_from_profile_url(profile_url)
    else:
        profile_url = None

    if username is None or profile_url is None:
        return None

    return BloggerProfile(
        input_url=input_url,
        profile_url=profile_url,
        username=username,
        full_name=_first_text(item, ("fullName", "name")),
        biography=_first_text(item, ("biography", "bio")),
        followers_count=_to_int(_first_existing(item, ("followersCount", "followers"))),
        follows_count=_to_int(_first_existing(item, ("followsCount", "followingCount", "follows"))),
        posts_count=_to_int(_first_existing(item, ("postsCount", "posts"))),
        verified=_to_bool(_first_existing(item, ("verified", "isVerified"))),
        private=_to_bool(_first_existing(item, ("private", "isPrivate"))),
        business_account=_to_bool(_first_existing(item, ("isBusinessAccount", "businessAccount"))),
        business_category_name=_first_text(item, ("businessCategoryName", "categoryName")),
        external_url=_first_text(item, ("externalUrl", "externalURL")),
        public_email=_first_text(item, ("publicEmail", "businessEmail", "email")),
        public_phone_number=_first_text(item, ("publicPhoneNumber", "businessPhoneNumber", "phoneNumber")),
        profile_pic_url=_first_text(item, ("profilePicUrl", "profilePicUrlHD", "profilePictureUrl")),
        raw_data=dict(item),
    )


class ApifyService:
    def __init__(
        self,
        api_token: str,
        actor_id: str,
        timeout_seconds: float,
    ) -> None:
        self.api_token = api_token
        self.actor_id = actor_id
        self.timeout_seconds = timeout_seconds

    def load_profiles(self, profile_urls: list[str]) -> ApifyEnrichmentResult:
        self._validate_settings(profile_urls)
        unique_urls = _unique_non_empty(profile_urls)
        if not unique_urls:
            raise ApifyServiceError("Список Instagram-профилей для Apify пуст.")

        endpoint = self._endpoint()
        payload = {
            "directUrls": unique_urls,
            "resultsType": "details",
            "resultsLimit": 1,
        }

        logger.info("Starting Apify run.")
        logger.info("Sending %s Instagram URLs to Apify.", len(unique_urls))

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    endpoint,
                    params={
                        "token": self.api_token,
                        "clean": "true",
                        "format": "json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as e:
            raise ApifyServiceError("Apify request timed out.") from e
        except httpx.ConnectError as e:
            raise ApifyServiceError("Не удалось подключиться к Apify.") from e
        except httpx.RequestError as e:
            raise ApifyServiceError("Ошибка HTTP-запроса к Apify.") from e

        self._raise_for_status(response)
        data = self._parse_json_response(response)
        if not isinstance(data, list):
            raise ApifyServiceError("Apify вернул неожиданный формат ответа: ожидался список.")

        self._save_raw_response(data)

        result = ApifyEnrichmentResult()
        for index, item in enumerate(data):
            fallback_url = unique_urls[index] if index < len(unique_urls) else ""
            if not isinstance(item, dict):
                failed_profile = FailedProfile(
                    input_url=fallback_url,
                    error_code="parse_error",
                    error_description="Dataset item is not an object.",
                    retryable=False,
                )
                result.failed_profiles.append(failed_profile)
                _log_failed_profile(failed_profile)
                continue

            error_code = _first_text(item, ("error",))
            if error_code:
                failed_profile = _failed_profile_from_item(item, fallback_url, error_code)
                result.failed_profiles.append(failed_profile)
                _log_failed_profile(failed_profile)
                continue

            try:
                profile = parse_apify_profile(item)
            except Exception as e:
                logger.warning("Apify profile parse failed. error_type=%s", type(e).__name__)
                failed_profile = FailedProfile(
                    input_url=_profile_input_url(item, fallback_url),
                    username=_profile_username(item),
                    error_code="parse_error",
                    error_description="Parser failed to process dataset item.",
                    retryable=False,
                )
                result.failed_profiles.append(failed_profile)
                _log_failed_profile(failed_profile)
                continue

            if profile is None:
                failed_profile = FailedProfile(
                    input_url=_profile_input_url(item, fallback_url),
                    username=_profile_username(item),
                    error_code="parse_error",
                    error_description="Could not parse BloggerProfile from dataset item.",
                    retryable=False,
                )
                result.failed_profiles.append(failed_profile)
                _log_failed_profile(failed_profile)
                continue

            result.profiles.append(profile)

        logger.info("Apify run completed.")
        logger.info("Apify dataset items: %s.", len(data))
        logger.info("Parsed BloggerProfile items: %s.", len(result.profiles))
        logger.info("Failed Apify profile items: %s.", len(result.failed_profiles))
        logger.info(
            "Apify enrichment completed: requested=%s parsed=%s failed=%s",
            len(unique_urls),
            len(result.profiles),
            len(result.failed_profiles),
        )

        return result

    def enrich_profiles(self, profile_urls: list[str]) -> ApifyEnrichmentResult:
        return self.load_profiles(profile_urls)

    def _validate_settings(self, profile_urls: list[str]) -> None:
        if not self.api_token:
            raise ApifyServiceError("Не задан APIFY_API_TOKEN.")

        if not self.actor_id:
            raise ApifyServiceError("Не задан APIFY_ACTOR_ID.")

        if self.timeout_seconds <= 0:
            raise ApifyServiceError("APIFY_REQUEST_TIMEOUT_SECONDS должен быть больше 0.")

        if not profile_urls:
            raise ApifyServiceError("Список Instagram-профилей для Apify пуст.")

    def _endpoint(self) -> str:
        actor_id = self.actor_id.strip().replace("/", "~")
        return f"https://api.apify.com/v2/actors/{actor_id}/run-sync-get-dataset-items"

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        response_text = response.text.lower()

        if status_code < 400:
            return

        if status_code in {401, 403}:
            raise ApifyServiceError("Apify отклонил авторизацию. Проверьте APIFY_API_TOKEN.")

        if status_code == 429:
            raise ApifyServiceError("Apify вернул ограничение частоты запросов.")

        if status_code >= 500:
            raise ApifyServiceError("Apify временно недоступен или вернул серверную ошибку.")

        if status_code == 402 or "balance" in response_text or "limit" in response_text:
            raise ApifyServiceError("Apify сообщил об ограничении, лимите или недостаточном балансе.")

        raise ApifyServiceError(f"Apify вернул HTTP {status_code}.")

    def _parse_json_response(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as e:
            raise ApifyServiceError("Apify вернул некорректный JSON.") from e

    def _save_raw_response(self, dataset: list[Any]) -> None:
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        output_path = results_dir / "apify_raw_response.json"

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(
                dataset,
                file,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("Apify raw response saved to results/apify_raw_response.json")


def _first_existing(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def _first_text(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    value = _first_existing(item, keys)
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _failed_profile_from_item(
    item: dict[str, Any],
    fallback_url: str,
    error_code: str,
) -> FailedProfile:
    return FailedProfile(
        input_url=_profile_input_url(item, fallback_url),
        username=_profile_username(item),
        error_code=error_code,
        error_description=_first_text(item, ("errorDescription",)),
        retryable=_is_retryable_profile_error(error_code),
    )


def _profile_input_url(item: dict[str, Any], fallback_url: str) -> str:
    return _first_text(item, ("url", "profileUrl", "inputUrl")) or fallback_url


def _profile_username(item: dict[str, Any]) -> str | None:
    username = _first_text(item, ("username", "ownerUsername"))
    if username is not None:
        return username

    profile_url = _first_text(item, ("url", "profileUrl", "inputUrl"))
    return _username_from_profile_url(profile_url)


def _is_retryable_profile_error(error_code: str) -> bool:
    normalized_error_code = error_code.strip().lower()
    if normalized_error_code in _NON_RETRYABLE_PROFILE_ERRORS:
        return False
    if normalized_error_code in _RETRYABLE_PROFILE_ERRORS:
        return True
    return False


def _log_failed_profile(failed_profile: FailedProfile) -> None:
    logger.warning(
        "Apify profile failed: username=%s error_code=%s retryable=%s url=%s",
        failed_profile.username or "-",
        failed_profile.error_code,
        failed_profile.retryable,
        failed_profile.input_url,
    )


def _to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _username_from_profile_url(profile_url: str | None) -> str | None:
    if profile_url is None:
        return None
    normalized = normalize_instagram_profile_url(profile_url)
    if normalized is None:
        return None
    return normalized.rstrip("/").split("/")[-1] or None


def _unique_non_empty(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique_values.append(text)

    return unique_values
