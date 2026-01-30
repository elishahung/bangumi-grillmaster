from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    fun_asr_model: str = Field(
        default="fun-asr-2025-11-07",
        description="Model identifier for ASR (Automatic Speech Recognition) processing",
    )
    gemini_model: str = Field(
        default="gemini-3-pro-preview",
        description="Model identifier for translation tasks",
    )
    cookies_txt_path: Path | None = Field(
        default=None,
        description="Path to cookies.txt file used for downloading content",
    )
    archived_path: Path | None = Field(
        default=None,
        description="Path for automatic archival. If set, completed projects will be archived to this location",
    )

    dashscope_api_key: str = Field(
        description="API key for DashScope service (Alibaba Cloud)"
    )
    oss_region: str = Field(
        description="Alibaba Cloud OSS region. Used for temporary storage of ASR files due to limited external network access from Alibaba Cloud"
    )
    oss_bucket: str = Field(
        description="Alibaba Cloud OSS bucket name. Used for temporary storage of ASR files due to limited external network access from Alibaba Cloud"
    )
    oss_access_key_id: str = Field(
        description="Alibaba Cloud OSS access key ID for authentication"
    )
    oss_access_key_secret: str = Field(
        description="Alibaba Cloud OSS access key secret for authentication"
    )
    gemini_api_key: str = Field(description="API key for Google Gemini service")


settings = Settings()
