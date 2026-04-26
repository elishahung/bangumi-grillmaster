"""ElevenLabs Speech to Text integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elevenlabs.client import ElevenLabs
from loguru import logger

from settings import settings


class ElevenLabsASR:
    """Client for synchronous ElevenLabs Scribe transcription."""

    def __init__(self) -> None:
        if not settings.elevenlabs_api_key:
            raise ValueError("ElevenLabs ASR requires ELEVENLABS_API_KEY")
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)

    def transcribe_to_file(
        self,
        audio_path: Path,
        json_path: Path,
    ) -> None:
        """Transcribe an audio file and persist the raw JSON response."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Submitting ElevenLabs STT request: {audio_path}")
        with audio_path.open("rb") as audio_file:
            response = self.client.speech_to_text.convert(
                file=audio_file,
                model_id=settings.elevenlabs_stt_model,
                language_code=settings.elevenlabs_stt_language_code,
                timestamps_granularity="word",
                diarize=True,
            )

        payload = _to_jsonable(response)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        logger.success(f"Saved ElevenLabs STT response: {json_path}")


def _to_jsonable(value: Any) -> Any:
    """Convert SDK response objects into JSON-serializable data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value
