from __future__ import annotations

from src.models.analyzed_candidate import AnalyzedCandidate
from src.models.blogger import BloggerProfile
from src.models.blogger_match_result import BloggerMatchResult
from src.models.ideal_blogger_profile import IdealBloggerProfile
from src.services.llm_service import LLMService
from src.services.matcher_prompt_builder import MatcherPromptBuilder
from src.services.prompt_builder import PromptBuilder
from src.utils.logger import logger


class MatcherService:
    def __init__(
        self,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        matcher_prompt_builder: MatcherPromptBuilder | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_service = llm_service
        self._matcher_prompt_builder = matcher_prompt_builder or MatcherPromptBuilder()

    def match(
        self,
        ideal_profile: IdealBloggerProfile,
        candidate_profile: BloggerProfile,
    ) -> BloggerMatchResult:
        logger.info("Blogger match started: username=%s", candidate_profile.username)

        try:
            system_prompt = self._matcher_prompt_builder.build_system_prompt()
            user_prompt = self._matcher_prompt_builder.build_user_prompt(
                ideal_profile=ideal_profile,
                candidate_profile=candidate_profile,
            )
            match_result = self._llm_service.analyze_match(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.error(
                "Blogger match failed: username=%s error_type=%s",
                candidate_profile.username,
                type(exc).__name__,
            )
            raise

        logger.info(
            "Blogger match completed: username=%s score=%s decision=%s",
            candidate_profile.username,
            match_result.final_score,
            match_result.decision.value,
        )
        return match_result

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
