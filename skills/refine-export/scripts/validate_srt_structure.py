"""Validate that a refined SRT preserves source block indexes and timecodes."""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SrtBlock:
    index: int
    timecode: str
    text: str


_BLOCK_RE = re.compile(r"\n\s*\n")


def parse_srt(path: Path) -> list[SrtBlock]:
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return []

    blocks: list[SrtBlock] = []
    for position, chunk in enumerate(_BLOCK_RE.split(raw), start=1):
        lines = chunk.splitlines()
        if len(lines) < 2:
            raise ValueError(f"block {position} has fewer than 2 lines")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise ValueError(f"block {position} has invalid index: {lines[0]!r}") from exc
        timecode = lines[1].strip()
        if "-->" not in timecode:
            raise ValueError(f"block {index} has invalid timecode: {timecode!r}")
        text = "\n".join(lines[2:]).strip()
        blocks.append(SrtBlock(index=index, timecode=timecode, text=text))
    return blocks


def validate(source_path: Path, refined_path: Path) -> list[str]:
    source = parse_srt(source_path)
    refined = parse_srt(refined_path)
    errors: list[str] = []

    if len(source) != len(refined):
        errors.append(f"block count differs: source={len(source)} refined={len(refined)}")

    for position, (left, right) in enumerate(zip(source, refined), start=1):
        if left.index != right.index:
            errors.append(f"position {position}: index changed {left.index} -> {right.index}")
        if left.timecode != right.timecode:
            errors.append(
                f"block {left.index}: timecode changed {left.timecode!r} -> {right.timecode!r}"
            )
        if not right.text:
            errors.append(f"block {right.index}: refined text is empty")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Original SRT, usually video.cht.srt")
    parser.add_argument("refined", type=Path, help="Refined SRT, usually video.cht.refined.srt")
    args = parser.parse_args()

    errors = validate(args.source, args.refined)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    refined = parse_srt(args.refined)
    print(f"SRT structure valid: {len(refined)} blocks, indexes and timecodes preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
