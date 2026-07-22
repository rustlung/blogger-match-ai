from __future__ import annotations

from pydantic import BaseModel


class FailedProfile(BaseModel):
    input_url: str
    username: str | None = None
    error_code: str
    error_description: str | None = None
    retryable: bool = False
