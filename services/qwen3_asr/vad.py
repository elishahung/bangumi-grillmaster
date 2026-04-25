"""VAD-based chunking for local Qwen3-ASR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from settings import settings
from services.media import WAV_SAMPLE_RATE


@dataclass(frozen=True)
class AudioChunk:
    start_sample: int
    end_sample: int

    @property
    def start_ms(self) -> int:
        return round(self.start_sample * 1000 / WAV_SAMPLE_RATE)

    @property
    def end_ms(self) -> int:
        return round(self.end_sample * 1000 / WAV_SAMPLE_RATE)


def plan_vad_chunks(
    total_samples: int,
    speech_timestamps: list[dict[str, int]],
    segment_threshold_s: int = 120,
    max_segment_threshold_s: int = 180,
    sample_rate: int = WAV_SAMPLE_RATE,
) -> list[AudioChunk]:
    """Plan ASR chunks around VAD speech boundaries."""

    if total_samples <= 0:
        return []
    if segment_threshold_s <= 0 or max_segment_threshold_s <= 0:
        raise ValueError("segment thresholds must be positive")

    max_samples = max_segment_threshold_s * sample_rate
    if total_samples <= max_samples:
        return [AudioChunk(0, total_samples)]

    if not speech_timestamps:
        return [
            AudioChunk(start, min(start + max_samples, total_samples))
            for start in range(0, total_samples, max_samples)
        ]

    potential_split_points = {0, total_samples}
    for timestamp in speech_timestamps:
        start = int(timestamp.get("start", 0))
        if 0 < start < total_samples:
            potential_split_points.add(start)

    sorted_potential_splits = sorted(potential_split_points)
    target_samples = segment_threshold_s * sample_rate
    final_split_points = {0, total_samples}
    target = target_samples
    while target < total_samples:
        closest = min(
            sorted_potential_splits,
            key=lambda point: abs(point - target),
        )
        final_split_points.add(closest)
        target += target_samples

    ordered_splits = sorted(final_split_points)
    enforced_splits = [ordered_splits[0]]
    for end in ordered_splits[1:]:
        start = enforced_splits[-1]
        segment_length = end - start
        if segment_length <= max_samples:
            enforced_splits.append(end)
            continue

        subsegment_count = -(-segment_length // max_samples)
        subsegment_length = segment_length / subsegment_count
        for index in range(1, subsegment_count):
            enforced_splits.append(round(start + index * subsegment_length))
        enforced_splits.append(end)

    deduped = sorted(set(enforced_splits))
    return [
        AudioChunk(start, end)
        for start, end in zip(deduped, deduped[1:])
        if end > start
    ]


def detect_speech_chunks(wav: Any) -> list[AudioChunk]:
    from silero_vad import get_speech_timestamps, load_silero_vad

    vad_model = load_silero_vad(onnx=True)
    speech_timestamps = get_speech_timestamps(
        wav,
        vad_model,
        sampling_rate=WAV_SAMPLE_RATE,
        return_seconds=False,
        min_speech_duration_ms=1500,
        min_silence_duration_ms=500,
    )

    return plan_vad_chunks(
        total_samples=len(wav),
        speech_timestamps=speech_timestamps,
        segment_threshold_s=settings.qwen3_asr_vad_segment_seconds,
        max_segment_threshold_s=settings.qwen3_asr_vad_max_segment_seconds,
    )
