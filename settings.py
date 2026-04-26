from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- ASR: ElevenLabs Scribe ---------------------------------------------
    elevenlabs_api_key: str | None = Field(
        default=None,
        description="API key for ElevenLabs Speech to Text",
    )
    elevenlabs_stt_model: str = Field(
        default="scribe_v2",
        description="ElevenLabs Speech to Text model identifier",
    )
    elevenlabs_stt_language_code: str = Field(
        default="jpn",
        description="Language code hint for ElevenLabs Speech to Text",
    )
    elevenlabs_srt_max_characters_per_line: int = Field(
        default=24,
        description="Maximum characters per rendered source SRT line",
    )
    elevenlabs_srt_max_segment_chars: int = Field(
        default=48,
        description="Maximum text characters per source SRT subtitle block",
    )
    elevenlabs_srt_max_segment_duration_s: float = Field(
        default=4,
        description="Maximum duration in seconds per source SRT subtitle block",
    )
    elevenlabs_srt_segment_on_silence_longer_than_s: float = Field(
        default=0.5,
        description="Split source SRT segments when silence exceeds this duration",
    )
    elevenlabs_srt_merge_speaker_turns_gap_s: float = Field(
        default=0.1,
        description="Merge adjacent speaker turns into one dialogue subtitle when the gap is below this duration",
    )
    elevenlabs_srt_max_lines_per_block: int = Field(
        default=3,
        description="Maximum rendered lines per source SRT subtitle block",
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
