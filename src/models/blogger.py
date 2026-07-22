from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BloggerProfile(BaseModel):
    input_url: str | None = Field(default=None)
    profile_url: str
    username: str
    full_name: str | None = Field(default=None)
    biography: str | None = Field(default=None)
    followers_count: int | None = Field(default=None)
    follows_count: int | None = Field(default=None)
    posts_count: int | None = Field(default=None)
    verified: bool | None = Field(default=None)
    private: bool | None = Field(default=None)
    business_account: bool | None = Field(default=None)
    business_category_name: str | None = Field(default=None)
    external_url: str | None = Field(default=None)
    public_email: str | None = Field(default=None)
    public_phone_number: str | None = Field(default=None)
    profile_pic_url: str | None = Field(default=None)
    raw_data: dict[str, Any]

    model_config = ConfigDict(extra="ignore")
