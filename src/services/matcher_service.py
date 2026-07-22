from __future__ import annotations

from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.blogger import BloggerProfile
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.llm_service import LLMService
from src.services.prompt_builder import PromptBuilder
from src.utils.logger import logger


class MatcherService:
    def __init__(
        self,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service

    def match_candidate(
        self,
        ideal_profile: IdealBloggerProfile,
        blogger: BloggerProfile,
    ) -> AnalyzedCandidate:
        logger.info("Candidate matching started: username=%s", blogger.username)

        try:
            system_prompt = self._prompt_builder.build_system_prompt()
            user_prompt = self._prompt_builder.build_user_prompt(
                ideal_profile=ideal_profile,
                blogger=blogger,
            )
            analysis = self._llm_service.analyze_candidate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.error(
                "Candidate matching failed: username=%s error_type=%s",
                blogger.username,
                type(exc).__name__,
            )
            raise

        logger.info(
            "Candidate matching completed: username=%s score=%s",
            blogger.username,
            analysis.overall_score,
        )
        return AnalyzedCandidate(
            blogger=blogger,
            analysis=analysis,
        )
