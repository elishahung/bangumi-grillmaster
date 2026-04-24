from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    fun_asr_model: str = Field(
        default="fun-asr",
        description="Model identifier for ASR (Automatic Speech Recognition) processing",
    )
    gemini_model: str = Field(
        default="gemini-3-flash-preview",
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
    dashscope_api_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1",
        description="Base HTTP API URL for DashScope service (Alibaba Cloud)",
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
    gemini_chunk_char_limit: int = Field(
        default=6000,
        description="Target character count per chunk when splitting SRT for concurrent translation (~5 min of variety show subtitles)",
    )
    gemini_concurrency: int = Field(
        default=10,
        description="Maximum number of concurrent chunk translation requests to Gemini",
    )
    gemini_thinking_level: str = Field(
        default="HIGH",
        description="Thinking level for translation calls. One of: LOW, MEDIUM, HIGH",
    )
    gemini_chunk_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts per chunk on translation failure",
    )

    llm_api_key: str = Field(
        description="API key forwarded to litellm for non-Gemini LLM calls (e.g., OpenRouter for the chunk-fix model)"
    )
    llm_chunk_fix_model: str = Field(
        default="openrouter/deepseek/deepseek-v4-flash",
        description="litellm model string used to repair chunk outputs that fail structural validation before falling back to a full chunk retry",
    )
    llm_chunk_fix_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for the structural fix layer per broken chunk output",
    )


settings = Settings()
