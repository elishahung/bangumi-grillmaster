"""ASR provider selection."""

from typing import Any

from settings import settings


def get_asr_client() -> Any:
    if settings.asr_provider == "fun_asr":
        from services.fun_asr import FunASR

        return FunASR()
    if settings.asr_provider == "qwen3_asr":
        from services.qwen3_asr import Qwen3ASR

        return Qwen3ASR()
    raise ValueError(f"Unsupported ASR provider: {settings.asr_provider}")
