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
from pydantic import ValidationError

from src.models.candidate_analysis import CandidateAnalysis
from src.models.blogger_match_result import BloggerMatchResult
from src.utils.logger import logger


class LLMServiceError(RuntimeError):
    pass


class LLMService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout = timeout
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def analyze_candidate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> CandidateAnalysis:
        self._validate(system_prompt, user_prompt)

        logger.info("Starting LLM analysis request. model=%s", self._model)

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
                response_format=CandidateAnalysis,
            )
        except APITimeoutError as exc:
            logger.warning("LLM request failed. error_type=timeout")
            raise LLMServiceError("LLM request timed out.") from exc
        except APIConnectionError as exc:
            logger.warning("LLM request failed. error_type=connection")
            raise LLMServiceError("LLM API connection failed.") from exc
        except AuthenticationError as exc:
            logger.warning("LLM request failed. error_type=authentication")
            raise LLMServiceError("LLM authentication failed.") from exc
        except RateLimitError as exc:
            logger.warning("LLM request failed. error_type=rate_limit")
            raise LLMServiceError("LLM rate limit exceeded.") from exc
        except BadRequestError as exc:
            logger.warning("LLM request failed. error_type=bad_request")
            raise LLMServiceError("LLM API rejected the request.") from exc
        except APIError as exc:
            logger.warning("LLM request failed. error_type=api_error")
            raise LLMServiceError("LLM API request failed.") from exc

        message = completion.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise LLMServiceError(f"LLM refused to analyze the candidate: {refusal}")

        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise LLMServiceError("LLM response did not contain structured analysis.")

        logger.info("LLM analysis request completed. model=%s", self._model)
        return parsed

    def analyze_match(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> BloggerMatchResult:
        self._validate(system_prompt, user_prompt)

        logger.info("Starting LLM match request. model=%s", self._model)

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
                response_format=BloggerMatchResult,
            )
        except APITimeoutError as exc:
            logger.warning("LLM match request failed. error_type=timeout")
            raise LLMServiceError("LLM match request timed out.") from exc
        except APIConnectionError as exc:
            logger.warning("LLM match request failed. error_type=connection")
            raise LLMServiceError("LLM match API connection failed.") from exc
        except AuthenticationError as exc:
            logger.warning("LLM match request failed. error_type=authentication")
            raise LLMServiceError("LLM match authentication failed.") from exc
        except RateLimitError as exc:
            logger.warning("LLM match request failed. error_type=rate_limit")
            raise LLMServiceError("LLM match rate limit exceeded.") from exc
        except BadRequestError as exc:
            logger.warning("LLM match request failed. error_type=bad_request")
            raise LLMServiceError("LLM match API rejected the request.") from exc
        except APIError as exc:
            logger.warning("LLM match request failed. error_type=api_error")
            raise LLMServiceError("LLM match API request failed.") from exc
        except ValidationError as exc:
            logger.warning("LLM match request failed. error_type=validation")
            raise LLMServiceError("LLM match response failed validation.") from exc

        message = completion.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise LLMServiceError("LLM refused to match the candidate.")

        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise LLMServiceError("LLM response did not contain structured match result.")

        logger.info("LLM match request completed. model=%s", self._model)
        return parsed

    def _validate(self, system_prompt: str, user_prompt: str) -> None:
        if not self._api_key:
            raise LLMServiceError("OPENAI_API_KEY is not configured.")

        if not self._base_url:
            raise LLMServiceError("OPENAI_BASE_URL is not configured.")

        if not self._model:
            raise LLMServiceError("OPENAI_MODEL is not configured.")

        if self._timeout <= 0:
            raise LLMServiceError("OPENAI_REQUEST_TIMEOUT_SECONDS must be greater than 0.")

        if not system_prompt.strip():
            raise LLMServiceError("System prompt is empty.")

        if not user_prompt.strip():
            raise LLMServiceError("User prompt is empty.")
