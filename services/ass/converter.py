"""Convert translated SRT subtitles to styled ASS format.

Applies Traditional Chinese subtitle punctuation rules aligned with the
Netflix TC style guide: replace ``，``/``、``/``；`` with a single space,
remove ``。`` entirely, and trim leading/trailing whitespace per line.
Other punctuation (``？``/``！``/``「」``/``（）``/``……``/``：`` etc.) is
preserved as-is.
"""

import re
from pathlib import Path
from typing import Iterable

from loguru import logger

from services.gemini.chunker import SrtBlock, parse_srt

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,源泉圓體月 B,64,&H00FDFDFD,&H000000FF,&H00000000,&H7D000000,0,0,0,0,100,100,0,0,1,7,2,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

_PUNCT_TABLE = str.maketrans(
    {
        "，": " ",
        "、": " ",
        "；": " ",
        "。": "",
    }
)

_MULTI_SPACE = re.compile(r" {2,}")
_SRT_TIMECODE = re.compile(
    r"^\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*$"
)


def _clean_line(line: str) -> str:
    cleaned = line.translate(_PUNCT_TABLE)
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    return cleaned.strip()


def _clean_text(text: str) -> str:
    return "\n".join(_clean_line(line) for line in text.split("\n"))


def _format_ass_time(h: str, m: str, s: str, ms: str) -> str:
    # ASS uses centiseconds with single-digit hour: H:MM:SS.cc.
    # Aegisub truncates the millisecond → centisecond conversion.
    return f"{int(h)}:{m}:{s}.{int(ms) // 10:02d}"


def _srt_timecode_to_ass(srt_timecode: str) -> tuple[str, str]:
    match = _SRT_TIMECODE.match(srt_timecode)
    if not match:
        raise ValueError(f"Invalid SRT timecode: {srt_timecode!r}")
    sh, sm, ss, sms, eh, em, es, ems = match.groups()
    return _format_ass_time(sh, sm, ss, sms), _format_ass_time(eh, em, es, ems)


def _block_to_dialogue(block: SrtBlock) -> str:
    start, end = _srt_timecode_to_ass(block.timecode)
    text = _clean_text(block.text).replace("\n", "\\N")
    return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"


def _render(blocks: Iterable[SrtBlock]) -> str:
    dialogue_lines = [_block_to_dialogue(b) for b in blocks]
    return ASS_HEADER + "\n".join(dialogue_lines) + "\n"


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
) -> None:
    """Read an SRT file, clean Chinese punctuation, and write a styled ASS file."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    srt_text = input_path.read_text(encoding="utf-8")
    blocks = parse_srt(srt_text)
    ass_text = _render(blocks)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ass_text, encoding="utf-8")
    logger.success(f"Converted SRT to ASS: {output_path}")
