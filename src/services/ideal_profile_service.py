from __future__ import annotations

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from src.models.blogger import BloggerProfile
from src.models.ideal_profile_analysis import IdealProfileAnalysis
from src.services.ideal_profile_prompt_builder import IdealProfilePromptBuilder
from src.utils.logger import logger


class IdealProfileServiceError(RuntimeError):
    pass


class IdealProfileService:
    def __init__(
        self,
        prompt_builder: IdealProfilePromptBuilder,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout = timeout
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def build_ideal_profile(self, profiles: list[BloggerProfile]) -> IdealProfileAnalysis:
        self._validate(profiles)

        system_prompt = self._prompt_builder.build_system_prompt()
        user_prompt = self._prompt_builder.build_user_prompt(profiles)

        logger.info("Starting ideal profile LLM request. model=%s profiles=%s", self._model, len(profiles))

        try:
            completion = self._client.chat.completions.parse(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_format=IdealProfileAnalysis,
            )
        except APITimeoutError as exc:
            logger.warning("Ideal profile LLM request failed. error_type=timeout")
            raise IdealProfileServiceError("Ideal profile LLM request timed out.") from exc
        except APIConnectionError as exc:
            logger.warning("Ideal profile LLM request failed. error_type=connection")
            raise IdealProfileServiceError("Ideal profile LLM API connection failed.") from exc
        except AuthenticationError as exc:
            logger.warning("Ideal profile LLM request failed. error_type=authentication")
            raise IdealProfileServiceError("Ideal profile LLM authentication failed.") from exc
        except RateLimitError as exc:
            logger.warning("Ideal profile LLM request failed. error_type=rate_limit")
            raise IdealProfileServiceError("Ideal profile LLM rate limit exceeded.") from exc
        except BadRequestError as exc:
            logger.warning("Ideal profile LLM request failed. error_type=bad_request")
            raise IdealProfileServiceError("Ideal profile LLM API rejected the request.") from exc
        except APIError as exc:
            logger.warning("Ideal profile LLM request failed. error_type=api_error")
            raise IdealProfileServiceError("Ideal profile LLM API request failed.") from exc

        message = completion.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise IdealProfileServiceError("LLM refused to build the ideal profile.")

        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise IdealProfileServiceError("LLM response did not contain structured ideal profile analysis.")

        logger.info("Ideal profile LLM request completed. model=%s profiles=%s", self._model, len(profiles))
        return parsed

    def _validate(self, profiles: list[BloggerProfile]) -> None:
        if not profiles:
            raise IdealProfileServiceError("Reference profiles list is empty.")

        if not self._api_key:
            raise IdealProfileServiceError("OPENAI_API_KEY is not configured.")

        if not self._base_url:
            raise IdealProfileServiceError("OPENAI_BASE_URL is not configured.")

        if not self._model:
            raise IdealProfileServiceError("OPENAI_MODEL is not configured.")

        if self._timeout <= 0:
            raise IdealProfileServiceError("OPENAI_REQUEST_TIMEOUT_SECONDS must be greater than 0.")
