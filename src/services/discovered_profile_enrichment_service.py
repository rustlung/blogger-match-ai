from __future__ import annotations

from src.models.apify_enrichment_result import ApifyEnrichmentResult
from src.models.discovery import DiscoveryResult
from src.services.apify_service import ApifyService, ApifyServiceError
from src.utils.logger import logger


class DiscoveredProfileEnrichmentServiceError(RuntimeError):
    pass


class DiscoveredProfileEnrichmentService:
    def __init__(self, profile_loader: ApifyService) -> None:
        self._profile_loader = profile_loader

    def enrich_discovered_profiles(self, discovery_result: DiscoveryResult) -> ApifyEnrichmentResult:
        profile_urls = [candidate.profile_url for candidate in discovery_result.candidates]
        if not profile_urls:
            return ApifyEnrichmentResult()

        try:
            result = self._profile_loader.load_profiles(profile_urls)
        except ApifyServiceError as exc:
            raise DiscoveredProfileEnrichmentServiceError(
                "Не удалось загрузить найденные профили через Apify."
            ) from exc

        for failed_profile in result.failed_profiles:
            logger.warning(
                "Discovered profile enrichment failed: username=%s error_code=%s retryable=%s url=%s",
                failed_profile.username or "-",
                failed_profile.error_code,
                failed_profile.retryable,
                failed_profile.input_url,
            )

        return result
