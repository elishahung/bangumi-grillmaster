"""Local Qwen3-ASR provider.

The runtime-heavy dependencies are imported lazily so the rest of the
application and unit tests can run without downloading local ASR models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from settings import settings
from services.fun_asr.srt import convert_normalized_to_srt
from services.fun_asr.models import (
    FunASRResult,
    NormalizedSentence,
    NormalizedTranscript,
)
from services.media import MediaProcessor, WAV_SAMPLE_RATE
from services.qwen3_asr.vad import AudioChunk, detect_speech_chunks

LOCAL_TASK_PREFIX = "local:"
MAX_SUBTITLE_CHARS = 28
MAX_SUBTITLE_DURATION_MS = 5500
MAX_WORD_GAP_MS = 900
SENTENCE_END_PUNCTUATION = {"。", "！", "？", "!", "?"}
SOFT_SPLIT_PUNCTUATION = {"、", "，", ","}
ATTACHED_PUNCTUATION = (
    SENTENCE_END_PUNCTUATION
    | SOFT_SPLIT_PUNCTUATION
    | {
        ".",
        "…",
    }
)


def qwen_results_to_fun_asr_json(
    *,
    file_path: Path,
    total_samples: int,
    chunks: list[AudioChunk],
    results: list[Any],
) -> dict[str, Any]:
    """Convert Qwen ASR results into the existing FunASR-compatible JSON."""

    sentences: list[dict[str, Any]] = []
    transcript_texts: list[str] = []

    for chunk, result in zip(chunks, results):
        text = str(getattr(result, "text", "") or "").strip()
        if not text:
            continue
        transcript_texts.append(text)

        time_stamps = getattr(result, "time_stamps", None) or []
        chunk_sentences = _timestamp_rows_to_sentences(
            time_stamps=time_stamps,
            full_text=text,
            chunk=chunk,
            sentence_offset=len(sentences),
        )
        if not chunk_sentences:
            chunk_sentences = [
                {
                    "begin_time": chunk.start_ms,
                    "end_time": chunk.end_ms,
                    "text": text,
                    "sentence_id": len(sentences),
                    "speaker_id": None,
                    "words": [],
                }
            ]
        sentences.extend(chunk_sentences)

    duration_ms = round(total_samples * 1000 / WAV_SAMPLE_RATE)
    return {
        "file_url": str(file_path),
        "properties": {
            "audio_format": file_path.suffix.lstrip(".") or "unknown",
            "channels": [0],
            "original_sampling_rate": WAV_SAMPLE_RATE,
            "original_duration_in_milliseconds": duration_ms,
        },
        "transcripts": [
            {
                "channel_id": 0,
                "content_duration_in_milliseconds": duration_ms,
                "text": " ".join(transcript_texts),
                "sentences": sentences,
            }
        ],
    }


def _timestamp_rows_to_sentences(
    *,
    time_stamps: Any,
    full_text: str,
    chunk: AudioChunk,
    sentence_offset: int,
) -> list[dict[str, Any]]:
    words = _timestamp_rows_to_words(time_stamps, chunk, full_text)
    if not words:
        return []

    return _words_to_sentences(words, sentence_offset)


def _words_to_sentences(
    words: list[dict[str, Any]],
    sentence_offset: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_words: list[dict[str, Any]] = []
    current_text = ""

    for word in words:
        word_text = word["text"] + word.get("punctuation", "")
        if not word_text:
            continue

        should_flush_before = False
        if current_words:
            gap_ms = word["begin_time"] - current_words[-1]["end_time"]
            duration_ms = word["end_time"] - current_words[0]["begin_time"]
            should_flush_before = (
                (
                    gap_ms >= MAX_WORD_GAP_MS
                    and not _is_short_continuation(word_text)
                )
                or len(current_text + word_text) > MAX_SUBTITLE_CHARS
                or (
                    duration_ms > MAX_SUBTITLE_DURATION_MS
                    and not _is_short_continuation(word_text)
                )
            )

        if should_flush_before:
            rows.append(
                _build_sentence_row(
                    words=current_words,
                    sentence_id=sentence_offset + len(rows),
                )
            )
            current_words = []
            current_text = ""

        current_words.append(word)
        current_text += word_text

        if word_text[-1] in SENTENCE_END_PUNCTUATION or (
            len(current_text) >= int(MAX_SUBTITLE_CHARS * 0.8)
            and word_text[-1] in SOFT_SPLIT_PUNCTUATION
        ):
            rows.append(
                _build_sentence_row(
                    words=current_words,
                    sentence_id=sentence_offset + len(rows),
                )
            )
            current_words = []
            current_text = ""

    if current_words:
        rows.append(
            _build_sentence_row(
                words=current_words,
                sentence_id=sentence_offset + len(rows),
            )
        )

    return rows


def _timestamp_rows_to_words(
    time_stamps: Any,
    chunk: AudioChunk,
    full_text: str,
) -> list[dict[str, Any]]:
    items = getattr(time_stamps, "items", time_stamps) or []
    items = list(items)
    if not items:
        return []

    raw_end_times = [
        float(end_time)
        for item in items
        if (end_time := _get_timestamp_value(item, "end_time")) is not None
    ]
    max_raw_end = max(raw_end_times, default=0.0)
    chunk_duration_seconds = max(
        0.001,
        (chunk.end_sample - chunk.start_sample) / WAV_SAMPLE_RATE,
    )
    raw_times_are_seconds = max_raw_end <= chunk_duration_seconds + 1.0

    words: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            text_value = item.get("text", "")
        else:
            text_value = getattr(item, "text", "")
        text = str(text_value or "").strip()
        if not text:
            continue

        start_time = _get_timestamp_value(item, "start_time")
        end_time = _get_timestamp_value(item, "end_time")
        if start_time is None or end_time is None:
            continue

        begin_time = chunk.start_ms + _raw_timestamp_to_ms(
            float(start_time),
            raw_times_are_seconds,
        )
        end_time = chunk.start_ms + _raw_timestamp_to_ms(
            float(end_time),
            raw_times_are_seconds,
        )
        begin_time = max(chunk.start_ms, min(begin_time, chunk.end_ms))
        end_time = max(begin_time + 1, min(end_time, chunk.end_ms))
        words.append(
            {
                "begin_time": begin_time,
                "end_time": end_time,
                "text": text,
                "punctuation": "",
            }
        )

    words = _repair_degenerate_word_times(words, chunk)
    _attach_punctuation_from_text(words, full_text)
    return words


def _get_timestamp_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _raw_timestamp_to_ms(value: float, raw_times_are_seconds: bool) -> int:
    if raw_times_are_seconds:
        return round(value * 1000)
    return round(value)


def _build_sentence_row(
    *,
    words: list[dict[str, Any]],
    sentence_id: int,
) -> dict[str, Any]:
    return {
        "begin_time": words[0]["begin_time"],
        "end_time": words[-1]["end_time"],
        "text": "".join(
            word["text"] + word.get("punctuation", "") for word in words
        ),
        "sentence_id": sentence_id,
        "speaker_id": None,
        "words": words,
    }


def _is_short_continuation(text: str) -> bool:
    text = text.rstrip("".join(ATTACHED_PUNCTUATION))
    return text in {
        "じゃ",
        "や",
        "よ",
        "ね",
        "な",
        "わ",
        "で",
        "て",
        "ん",
        "は",
        "が",
        "を",
        "に",
        "の",
        "と",
    }


def _repair_degenerate_word_times(
    words: list[dict[str, Any]],
    chunk: AudioChunk,
) -> list[dict[str, Any]]:
    if not words:
        return words

    repaired = [dict(word) for word in words]
    index = 0
    while index < len(repaired):
        word = repaired[index]
        if word["end_time"] - word["begin_time"] > 1:
            index += 1
            continue

        group_start = index
        begin_time = word["begin_time"]
        while (
            index + 1 < len(repaired)
            and repaired[index + 1]["begin_time"] == begin_time
            and repaired[index + 1]["end_time"]
            - repaired[index + 1]["begin_time"]
            <= 1
        ):
            index += 1
        group_end = index

        next_begin = None
        for next_word in repaired[group_end + 1 :]:
            if next_word["begin_time"] > begin_time:
                next_begin = next_word["begin_time"]
                break

        fallback_duration = max(
            400,
            sum(len(w["text"]) for w in repaired[group_start : group_end + 1])
            * 120,
        )
        end_boundary = min(
            (
                next_begin
                if next_begin is not None
                else begin_time + fallback_duration
            ),
            chunk.end_ms,
        )
        if end_boundary <= begin_time:
            end_boundary = min(begin_time + fallback_duration, chunk.end_ms)

        cursor = begin_time
        total_chars = max(
            1,
            sum(len(w["text"]) for w in repaired[group_start : group_end + 1]),
        )
        total_duration = max(1, end_boundary - begin_time)
        for current_index in range(group_start, group_end + 1):
            current = repaired[current_index]
            weight = max(1, len(current["text"]))
            duration = max(1, round(total_duration * weight / total_chars))
            current["begin_time"] = cursor
            current["end_time"] = min(end_boundary, cursor + duration)
            cursor = current["end_time"]

        repaired[group_end]["end_time"] = max(
            repaired[group_end]["end_time"],
            end_boundary,
        )
        index += 1

    return repaired


def _attach_punctuation_from_text(
    words: list[dict[str, Any]],
    full_text: str,
) -> None:
    if not words or not full_text:
        return

    position = 0
    for index, word in enumerate(words):
        text = word["text"]
        found_at = full_text.find(text, position)
        if found_at < 0:
            continue

        cursor = found_at + len(text)
        punctuation = ""
        while cursor < len(full_text):
            char = full_text[cursor]
            if char.isspace():
                cursor += 1
                continue
            if char in ATTACHED_PUNCTUATION:
                punctuation += char
                cursor += 1
                continue
            break

        word["punctuation"] = punctuation
        position = cursor


class Qwen3ASR:
    """Local Qwen3-ASR service with the same workflow-facing API as FunASR."""

    def __init__(self):
        self._model: Any | None = None

    def submit_transcription_task(self, key: str, file_path: Path) -> str:
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        task_id = f"{LOCAL_TASK_PREFIX}{key}"
        logger.info(f"Prepared local Qwen3-ASR task: {task_id}")
        return task_id

    def process_transcription_task(
        self, key: str, task_id: str, json_path: Path
    ) -> None:
        expected_task_id = f"{LOCAL_TASK_PREFIX}{key}"
        if task_id != expected_task_id:
            raise ValueError(
                f"Invalid Qwen3-ASR task id: {task_id}; expected {expected_task_id}"
            )

        audio_path = json_path.parent / "audio.opus"
        logger.info(f"Running local Qwen3-ASR for: {audio_path}")
        wav = MediaProcessor.load_audio_waveform(audio_path)
        chunks = detect_speech_chunks(wav)
        logger.info(f"Qwen3-ASR VAD produced {len(chunks)} chunk(s)")

        audio_inputs = [
            (wav[chunk.start_sample : chunk.end_sample], WAV_SAMPLE_RATE)
            for chunk in chunks
        ]
        language = settings.qwen3_asr_language or None
        languages = [language for _ in audio_inputs]
        contexts = ["" for _ in audio_inputs]

        results = self._get_model().transcribe(
            audio=audio_inputs,
            context=contexts,
            language=languages,
            return_time_stamps=True,
        )

        output = qwen_results_to_fun_asr_json(
            file_path=audio_path,
            total_samples=len(wav),
            chunks=chunks,
            results=results,
        )

        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        logger.success(f"Qwen3-ASR result saved to: {json_path}")

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        import torch
        from qwen_asr import Qwen3ASRModel

        dtype = getattr(torch, settings.qwen3_asr_dtype)
        self._model = Qwen3ASRModel.from_pretrained(
            settings.qwen3_asr_model,
            dtype=dtype,
            device_map=settings.qwen3_asr_device_map,
            forced_aligner=settings.qwen3_asr_forced_aligner,
            forced_aligner_kwargs={
                "dtype": dtype,
                "device_map": settings.qwen3_asr_device_map,
            },
            max_inference_batch_size=settings.qwen3_asr_max_inference_batch_size,
            max_new_tokens=settings.qwen3_asr_max_new_tokens,
        )
        return self._model
