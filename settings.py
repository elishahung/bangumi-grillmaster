from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    fun_asr_model: str = "fun-asr-2025-11-07"
    gemini_model: str = "gemini-3-flash-preview"

    dashscope_api_key: str
    oss_region: str
    oss_bucket: str
    oss_access_key_id: str
    oss_access_key_secret: str
    gemini_api_key: str


settings = Settings()
