from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- ASR: routing --------------------------------------------------------
    asr_provider: Literal["fun_asr", "qwen3_asr"] = Field(
        default="fun_asr",
        description="ASR provider to use. fun_asr uses DashScope; qwen3_asr runs Qwen3-ASR locally.",
    )
    fun_asr_model: str = Field(
        default="fun-asr",
        description="Model identifier for ASR (Automatic Speech Recognition) processing",
    )

    # --- ASR: FunASR (DashScope + OSS; required when asr_provider=fun_asr) -----
    dashscope_api_key: str | None = Field(
        default=None,
        description="API key for DashScope service (Alibaba Cloud). Required when ASR_PROVIDER=fun_asr",
    )
    dashscope_api_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1",
        description="Base HTTP API URL for DashScope service (Alibaba Cloud)",
    )
    oss_region: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS region. Required when ASR_PROVIDER=fun_asr",
    )
    oss_bucket: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS bucket name. Required when ASR_PROVIDER=fun_asr",
    )
    oss_access_key_id: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS access key ID for authentication. Required when ASR_PROVIDER=fun_asr",
    )
    oss_access_key_secret: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS access key secret for authentication. Required when ASR_PROVIDER=fun_asr",
    )

    # --- ASR: local Qwen3 (when asr_provider=qwen3_asr) -----------------------
    qwen3_asr_model: str = Field(
        default="Qwen/Qwen3-ASR-1.7B",
        description="Qwen3-ASR model id or local checkpoint path",
    )
    qwen3_asr_forced_aligner: str = Field(
        default="Qwen/Qwen3-ForcedAligner-0.6B",
        description="Qwen3 forced aligner model id or local checkpoint path used for timestamps",
    )
    qwen3_asr_device_map: str = Field(
        default="cuda:0",
        description="Device map passed to Qwen3-ASR and forced aligner",
    )
    qwen3_asr_dtype: str = Field(
        default="bfloat16",
        description="Torch dtype name passed to Qwen3-ASR and forced aligner",
    )
    qwen3_asr_max_inference_batch_size: int = Field(
        default=8,
        description="Maximum Qwen3-ASR inference batch size",
    )
    qwen3_asr_max_new_tokens: int = Field(
        default=1024,
        description="Maximum tokens generated per Qwen3-ASR chunk",
    )
    qwen3_asr_vad_segment_seconds: int = Field(
        default=120,
        description="Target duration in seconds for VAD-based Qwen3-ASR chunks",
    )
    qwen3_asr_vad_max_segment_seconds: int = Field(
        default=180,
        description="Hard maximum duration in seconds for Qwen3-ASR chunks",
    )
    qwen3_asr_language: str | None = Field(
        default="Japanese",
        description="Language hint passed to Qwen3-ASR. Set empty/null for automatic language detection",
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
