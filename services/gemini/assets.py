"""Chunk/pre-pass media asset builders and persistent cache manifests."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from services.media import MediaProcessor, TimeRange
from .chunker import SrtBlock
from .storage import GeminiFileRef


class FrameSpec(BaseModel):
    timestamp_seconds: float
    path: Path
    storage_key: str
    mime_type: str = "image/jpeg"


class ChunkMediaAssets(BaseModel):
    time_range: TimeRange
    audio: GeminiFileRef
    frames: list[FrameSpec]
    manifest_path: Path
    response_dir: Path


class PrePassMediaAssets(BaseModel):
    frames: list[FrameSpec]
    manifest_path: Path


def prepare_pre_pass_media_assets(
    video_path: Path,
    cache_root: Path,
    video_key: str,
    max_frames: int,
    max_side: int,
) -> PrePassMediaAssets:
    cache_root.mkdir(parents=True, exist_ok=True)
    frame_dir = cache_root / "media" / "frames"
    manifest_path = cache_root / "assets.json"

    duration = MediaProcessor.get_media_duration(video_path)
    timestamps = [
        round(ts, 3)
        for ts in MediaProcessor.evenly_spaced_timestamps(duration, max_frames)
    ]
    frames = [
        _build_frame_asset(
            video_path=video_path,
            output_dir=frame_dir,
            timestamp_seconds=timestamp,
            max_side=max_side,
            storage_key=(
                f"{video_key}:pre-pass:frame:{timestamp:.3f}:max_side={max_side}"
            ),
        )
        for timestamp in timestamps
    ]
    manifest_path.write_text(
        json.dumps(
            {
                "video_path": str(video_path),
                "duration_seconds": duration,
                "max_frames": max_frames,
                "max_side": max_side,
                "frames": [
                    {
                        "timestamp_seconds": frame.timestamp_seconds,
                        "path": str(frame.path),
                        "storage_key": frame.storage_key,
                    }
                    for frame in frames
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return PrePassMediaAssets(frames=frames, manifest_path=manifest_path)


def prepare_chunk_media_assets(
    video_path: Path,
    audio_path: Path,
    cache_root: Path,
    video_key: str,
    chunk: list[SrtBlock],
    chunk_index: int,
    total_chunks: int,
    interval_seconds: int,
    max_side: int,
    is_last_chunk: bool,
) -> ChunkMediaAssets:
    range_info = _chunk_time_range(chunk)
    chunk_slug = f"{chunk[0].index:04d}-{chunk[-1].index:04d}"

    manifests_dir = cache_root / "manifests"
    audio_dir = cache_root / "media" / "audio"
    frame_dir = cache_root / "media" / "frames"
    response_dir = cache_root / "responses"
    manifest_path = manifests_dir / f"chunk_{chunk_slug}.json"

    frame_timestamps = MediaProcessor.absolute_interval_timestamps(
        start_seconds=range_info.start_seconds,
        end_seconds=range_info.end_seconds,
        interval_seconds=interval_seconds,
        include_start=True,
        include_end=is_last_chunk,
    )

    digest = hashlib.sha256(
        (
            f"{video_key}:{chunk_slug}:{range_info.start_seconds:.3f}:"
            f"{range_info.end_seconds:.3f}:{interval_seconds}:{max_side}"
        ).encode("utf-8")
    ).hexdigest()[:10]
    audio_output = audio_dir / f"chunk_{chunk_slug}_{digest}.opus"
    MediaProcessor.extract_audio_segment(
        input_file=audio_path,
        output_file=audio_output,
        start_seconds=range_info.start_seconds,
        end_seconds=range_info.end_seconds,
    )

    audio_ref = GeminiFileRef(
        key=(
            f"{video_key}:chunk-audio:{chunk_slug}:"
            f"{range_info.start_seconds:.3f}:{range_info.end_seconds:.3f}"
        ),
        file_path=audio_output,
        mime_type="audio/ogg",
    )
    frames = [
        _build_frame_asset(
            video_path=video_path,
            output_dir=frame_dir,
            timestamp_seconds=timestamp,
            max_side=max_side,
            storage_key=(
                f"{video_key}:chunk-frame:{timestamp:.3f}:max_side={max_side}"
            ),
        )
        for timestamp in frame_timestamps
    ]

    manifests_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "from_index": chunk[0].index,
                "to_index": chunk[-1].index,
                "time_range": range_info.model_dump(),
                "interval_seconds": interval_seconds,
                "max_side": max_side,
                "audio": audio_ref.model_dump(mode="json"),
                "frames": [frame.model_dump(mode="json") for frame in frames],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ChunkMediaAssets(
        time_range=range_info,
        audio=audio_ref,
        frames=frames,
        manifest_path=manifest_path,
        response_dir=response_dir,
    )


def _chunk_time_range(chunk: list[SrtBlock]) -> TimeRange:
    start = MediaProcessor.parse_timecode_line(chunk[0].timecode).start_seconds
    end = MediaProcessor.parse_timecode_line(chunk[-1].timecode).end_seconds
    return TimeRange(start_seconds=start, end_seconds=end)


def _build_frame_asset(
    video_path: Path,
    output_dir: Path,
    timestamp_seconds: float,
    max_side: int,
    storage_key: str,
) -> FrameSpec:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"frame_{timestamp_seconds:010.3f}_{max_side}.jpg"
    output_path = output_dir / filename
    MediaProcessor.extract_video_frame(
        input_file=video_path,
        output_file=output_path,
        timestamp_seconds=timestamp_seconds,
        max_side=max_side,
    )
    return FrameSpec(
        timestamp_seconds=timestamp_seconds,
        path=output_path,
        storage_key=storage_key,
    )
