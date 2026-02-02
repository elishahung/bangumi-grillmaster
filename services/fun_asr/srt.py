"""Converter for FunASR JSON to SRT format with normalization."""

import json
from pathlib import Path
from typing import Union

from .models import FunASRResult, NormalizedTranscript
from .normalize import normalize_transcript


def ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def convert_normalized_to_srt(transcript: NormalizedTranscript) -> str:
    """
    Convert NormalizedTranscript to SRT format.

    Args:
        transcript: The normalized transcript to convert

    Returns:
        SRT formatted string
    """
    srt_lines: list[str] = []

    for idx, sentence in enumerate(transcript.sentences, start=1):
        if not sentence.text.strip():
            continue

        start_str = ms_to_srt_time(sentence.begin_time)
        end_str = ms_to_srt_time(sentence.end_time)

        srt_lines.append(f"{idx}")
        srt_lines.append(f"{start_str} --> {end_str}")
        srt_lines.append(sentence.text)
        srt_lines.append("")  # Empty line between entries

    return "\n".join(srt_lines)


def convert_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    channel_id: int = 0,
) -> None:
    """
    Convert a FunASR JSON file to SRT format.

    This function reads the raw FunASR JSON, normalizes it (merging dotted
    sentences, splitting long ones), and converts to SRT format.

    Args:
        input_path: Path to the FunASR JSON file
        output_path: Path to save the SRT file
        channel_id: Which audio channel to process (default: 0)
    """
    input_path = Path(input_path)

    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Parse and normalize
    data = FunASRResult.model_validate(raw_data)
    normalized = normalize_transcript(data, channel_id)

    # Convert to SRT
    srt_content = convert_normalized_to_srt(normalized)

    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
