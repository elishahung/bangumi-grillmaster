"""Pure functions for parsing, splitting, and serializing SRT subtitle blocks."""

import math
import re
from pydantic import BaseModel


class SrtBlock(BaseModel):
    """A single SRT subtitle entry: index, timecode, and text body."""

    index: int
    timecode: str
    text: str

    @property
    def raw(self) -> str:
        """Serialize this block back to SRT format (without trailing blank line)."""
        return f"{self.index}\n{self.timecode}\n{self.text}"

    @property
    def char_count(self) -> int:
        """Character count of the raw representation; used for chunk sizing."""
        return len(self.raw)


_BLOCK_SEPARATOR = re.compile(r"\r?\n\r?\n")
_TIMECODE_LINE = re.compile(
    r"^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}$"
)


def parse_srt(srt_text: str) -> list[SrtBlock]:
    """Parse raw SRT text into a list of SrtBlock.

    Tolerates trailing whitespace and CRLF line endings. Empty blocks (no text
    body) are preserved with an empty text field.
    """
    blocks: list[SrtBlock] = []
    for raw_block in _BLOCK_SEPARATOR.split(srt_text.strip()):
        lines = raw_block.strip().splitlines()
        if len(lines) < 2:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            raise ValueError(f"Invalid SRT index line: {lines[0]!r}")
        timecode = lines[1].strip()
        if not _TIMECODE_LINE.match(timecode):
            raise ValueError(f"Invalid SRT timecode line: {timecode!r}")
        text = "\n".join(lines[2:])
        blocks.append(SrtBlock(index=index, timecode=timecode, text=text))
    return blocks


def serialize_srt(blocks: list[SrtBlock]) -> str:
    """Serialize a list of SrtBlock back to SRT text with blank-line separators."""
    return "\n\n".join(b.raw for b in blocks) + "\n"


def split_into_chunks(
    blocks: list[SrtBlock], target_char_limit: int
) -> list[list[SrtBlock]]:
    """Split blocks into chunks of roughly equal character count.

    Strategy: compute total chars, derive N = ceil(total / limit), then greedily
    add blocks to each chunk until it reaches the average target. The final
    chunk receives whatever remains and may be shorter.

    SRT block boundaries are always preserved (blocks are never split).
    """
    if not blocks:
        return []
    if target_char_limit <= 0:
        raise ValueError("target_char_limit must be positive")

    total_chars = sum(b.char_count for b in blocks)
    num_chunks = max(1, math.ceil(total_chars / target_char_limit))
    if num_chunks >= len(blocks):
        # One block per chunk maximum; otherwise each chunk gets one block.
        return [[b] for b in blocks]

    target_per_chunk = total_chars / num_chunks
    chunks: list[list[SrtBlock]] = []
    current: list[SrtBlock] = []
    current_chars = 0

    for block in blocks:
        current.append(block)
        current_chars += block.char_count
        # Close the chunk when it reaches target, unless this is the last chunk
        # (in which case we absorb the rest).
        if (
            current_chars >= target_per_chunk
            and len(chunks) < num_chunks - 1
        ):
            chunks.append(current)
            current = []
            current_chars = 0

    if current:
        chunks.append(current)
    return chunks
