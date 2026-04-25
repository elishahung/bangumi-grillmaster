from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- ASR: FunASR (DashScope + OSS) --------------------------------------
    fun_asr_model: str = Field(
        default="fun-asr",
        description="Model identifier for ASR (Automatic Speech Recognition) processing",
    )
    dashscope_api_key: str | None = Field(
        default=None,
        description="API key for DashScope service (Alibaba Cloud)",
    )
    dashscope_api_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1",
        description="Base HTTP API URL for DashScope service (Alibaba Cloud)",
    )
    oss_region: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS region",
    )
    oss_bucket: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS bucket name",
    )
    oss_access_key_id: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS access key ID for authentication",
    )
    oss_access_key_secret: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS access key secret for authentication",
    )

    # --- Translation: Gemini -----------------------------------------------
    gemini_api_key: str = Field(description="API key for Google Gemini service")
    gemini_model: str = Field(
        default="gemini-3-flash-preview",
        description="Model identifier for translation tasks",
    )
    gemini_thinking_level: str = Field(
        default="HIGH",
        description="Thinking level for translation calls. One of: LOW, MEDIUM, HIGH",
    )
    gemini_pre_pass_max_frames: int = Field(
        default=10,
        description="Maximum number of evenly sampled reference frames attached to Gemini pre-pass",
    )
    gemini_pre_pass_frame_max_side: int = Field(
        default=768,
        description="Maximum pixel length of the longest side for pre-pass frame images",
    )
    gemini_chunk_char_limit: int = Field(
        default=6000,
        description="Target character count per chunk when splitting SRT for concurrent translation (~5 min of variety show subtitles)",
    )
    gemini_concurrency: int = Field(
        default=10,
        description="Maximum number of concurrent chunk translation requests to Gemini",
    )
    gemini_chunk_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts per chunk on translation failure",
    )
    gemini_chunk_frame_interval_seconds: int = Field(
        default=30,
        description="Absolute video frame sampling interval in seconds for chunk translation inputs",
    )
    gemini_chunk_frame_max_side: int = Field(
        default=768,
        description="Maximum pixel length of the longest side for chunk frame images",
    )
    gemini_chunk_missing_block_tolerance: int = Field(
        default=2,
        description="Maximum number of unmatched/missing subtitle blocks allowed per translated chunk before structural validation fails",
    )

    # --- Translation: structural fix (litellm, non-Gemini) -------------------
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

    # --- Download & pipeline extras -----------------------------------------
    cookies_txt_path: Path | None = Field(
        default=None,
        description="Path to cookies.txt file used for downloading content",
    )
    archived_path: Path | None = Field(
        default=None,
        description="Path for automatic archival. If set, completed projects will be archived to this location",
    )


settings = Settings()
