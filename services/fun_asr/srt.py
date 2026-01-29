"""
Converter for Aliyun FunASR JSON to SRT format.
"""

import json
from typing import Union
from pathlib import Path


def ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def convert_funasr_to_srt(data: dict, channel_id: int = 0) -> str:
    """
    Convert FunASR JSON response to SRT format.

    Args:
        data: The parsed JSON data from FunASR API
        channel_id: Which channel to extract (default: 0)

    Returns:
        SRT formatted string
    """
    srt_lines = []

    transcripts = data.get("transcripts", [])

    # Find the transcript for the specified channel
    transcript = None
    for t in transcripts:
        if t.get("channel_id") == channel_id:
            transcript = t
            break

    if not transcript:
        return ""

    sentences = transcript.get("sentences", [])

    for idx, sentence in enumerate(sentences, start=1):
        begin_time = sentence.get("begin_time", 0)
        end_time = sentence.get("end_time", 0)
        text = sentence.get("text", "")

        if not text.strip():
            continue

        start_str = ms_to_srt_time(begin_time)
        end_str = ms_to_srt_time(end_time)

        srt_lines.append(f"{idx}")
        srt_lines.append(f"{start_str} --> {end_str}")
        srt_lines.append(text)
        srt_lines.append("")  # Empty line between entries

    return "\n".join(srt_lines)


def convert_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    channel_id: int = 0,
) -> None:
    """
    Convert a FunASR JSON file to SRT format.

    Args:
        input_path: Path to the input JSON file
        output_path: Path to save the SRT file
        channel_id: Which channel to extract (default: 0)
    """
    input_path = Path(input_path)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    srt_content = convert_funasr_to_srt(data, channel_id)

    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
