"""Convert ElevenLabs word-level ASR JSON into source SRT subtitles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


JAPANESE_HARD_PUNCTUATION = "。！？?!"
JAPANESE_SOFT_PUNCTUATION = "、，,：:；;"
NO_SPACE_BEFORE = set("。、，,.！？?!：:；;）)]」』】》〉")
NO_SPACE_AFTER = set("（([「『【《〈")
JAPANESE_UNSAFE_SEGMENT_STARTS = {
    "を",
    "に",
    "へ",
    "で",
    "と",
    "は",
    "が",
    "の",
    "も",
    "や",
    "か",
    "な",
    "ね",
    "よ",
    "ぞ",
    "ぜ",
    "わ",
    "さ",
    "し",
    "て",
    "だ",
    "です",
    "ます",
}


@dataclass(frozen=True)
class SrtFormatOptions:
    """Formatting controls for local SRT generation."""

    max_characters_per_line: int = 24
    max_segment_chars: int = 48
    max_segment_duration_s: float = 5.5
    segment_on_silence_longer_than_s: float = 0.7
    merge_speaker_turns_gap_s: float = 0.45
    merge_same_speaker_gap_s: float = 0.25
    merge_overlapping_blocks: bool = True
    max_overlapping_block_duration_s: float = 8.0
    max_utterances_per_block: int = 5
    max_lines_per_block: int = 2
    inline_short_same_speaker_utterances: bool = True
    max_inline_short_utterance_chars: int = 8
    min_segment_duration_s: float = 0.35
    split_on_punctuation: str = JAPANESE_HARD_PUNCTUATION
    soft_split_punctuation: str = JAPANESE_SOFT_PUNCTUATION
    dialogue_prefix: str = "-"
    line_separator: str = "\n"
    include_speaker_prefix_for_dialogue: bool = True
    text_join_language: str = "ja"
    ignored_word_types: set[str] = field(
        default_factory=lambda: {"audio_event"}
    )


@dataclass(frozen=True)
class WordToken:
    text: str
    start: float
    end: float
    speaker_id: str | None


@dataclass
class Utterance:
    speaker_id: str | None
    start: float
    end: float
    text: str


@dataclass
class SubtitleBlock:
    start: float
    end: float
    utterances: list[Utterance]


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
    options: SrtFormatOptions | None = None,
) -> None:
    """Convert an ElevenLabs ASR JSON file to SRT."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    srt = convert_payload_to_srt(payload, options)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt, encoding="utf-8")
    logger.success(f"Converted ElevenLabs ASR JSON to SRT: {output_path}")


def convert_payload_to_srt(
    payload: dict[str, Any],
    options: SrtFormatOptions | None = None,
) -> str:
    """Convert an ElevenLabs ASR response payload to SRT text."""
    options = options or SrtFormatOptions()
    tokens = _extract_tokens(payload, options)
    if not tokens:
        raise ValueError("ElevenLabs ASR JSON does not contain timed words")

    utterances = _build_utterances(tokens, options)
    blocks = _merge_utterances_to_blocks(utterances, options)
    if options.merge_overlapping_blocks:
        blocks = _merge_overlapping_blocks(blocks, options)
    if options.inline_short_same_speaker_utterances:
        _inline_short_same_speaker_utterances(blocks, options)
    _resolve_block_overlaps(blocks, options)
    return _render_srt(blocks, options)


def _extract_tokens(
    payload: dict[str, Any], options: SrtFormatOptions
) -> list[WordToken]:
    word_items = _extract_word_items(payload)
    tokens: list[WordToken] = []
    for item in word_items:
        if not isinstance(item, dict):
            continue
        word_type = item.get("type")
        if word_type in options.ignored_word_types:
            continue
        text = str(item.get("text") or "")
        if not text:
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, (int, float)) or not isinstance(
            end, (int, float)
        ):
            continue
        if end < start:
            continue
        tokens.append(
            WordToken(
                text=text,
                start=float(start),
                end=float(end),
                speaker_id=item.get("speaker_id"),
            )
        )
    tokens.sort(key=lambda token: (token.start, token.end))
    return tokens


def _extract_word_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("words"), list):
        return payload["words"]

    transcripts = payload.get("transcripts")
    if isinstance(transcripts, list):
        words: list[dict[str, Any]] = []
        for transcript in transcripts:
            if isinstance(transcript, dict) and isinstance(
                transcript.get("words"), list
            ):
                words.extend(transcript["words"])
        return words

    return []


def _build_utterances(
    tokens: list[WordToken], options: SrtFormatOptions
) -> list[Utterance]:
    utterances: list[Utterance] = []
    current: list[WordToken] = []

    for token in tokens:
        if not current:
            current.append(token)
            continue

        previous = current[-1]
        if _should_start_new_utterance(current, previous, token, options):
            utterances.append(_tokens_to_utterance(current, options))
            current = [token]
        else:
            current.append(token)

    if current:
        utterances.append(_tokens_to_utterance(current, options))

    return [utterance for utterance in utterances if utterance.text]


def _should_start_new_utterance(
    current: list[WordToken],
    previous: WordToken,
    token: WordToken,
    options: SrtFormatOptions,
) -> bool:
    if token.speaker_id != previous.speaker_id:
        return True
    unsafe_start = _is_unsafe_segment_start(token.text)
    if (
        token.start - previous.end > options.segment_on_silence_longer_than_s
        and not unsafe_start
    ):
        return True

    text = _join_token_texts(current, options)
    prospective_text = _join_token_texts([*current, token], options)
    prospective_duration = token.end - current[0].start
    if _ends_with_split_punctuation(previous.text, options):
        return True
    if (
        _ends_with_soft_split_punctuation(previous.text, options)
        and len(text) >= options.max_characters_per_line
    ):
        return True
    if len(prospective_text) > options.max_segment_chars and not unsafe_start:
        return True
    return (
        prospective_duration > options.max_segment_duration_s
        and not unsafe_start
    )


def _tokens_to_utterance(
    tokens: list[WordToken], options: SrtFormatOptions
) -> Utterance:
    start = tokens[0].start
    end = max(tokens[-1].end, start + options.min_segment_duration_s)
    return Utterance(
        speaker_id=tokens[0].speaker_id,
        start=start,
        end=end,
        text=_join_token_texts(tokens, options).strip(),
    )


def _merge_utterances_to_blocks(
    utterances: list[Utterance], options: SrtFormatOptions
) -> list[SubtitleBlock]:
    blocks: list[SubtitleBlock] = []

    for utterance in utterances:
        if not blocks:
            blocks.append(
                SubtitleBlock(
                    start=utterance.start,
                    end=utterance.end,
                    utterances=[utterance],
                )
            )
            continue

        block = blocks[-1]
        if _can_merge_into_block(block, utterance, options):
            if block.utterances[-1].speaker_id == utterance.speaker_id:
                block.utterances[-1].text = _join_text_parts(
                    block.utterances[-1].text,
                    utterance.text,
                    options,
                )
                block.utterances[-1].end = utterance.end
            else:
                block.utterances.append(utterance)
            block.end = max(block.end, utterance.end)
        else:
            blocks.append(
                SubtitleBlock(
                    start=utterance.start,
                    end=utterance.end,
                    utterances=[utterance],
                )
            )

    return blocks


def _merge_overlapping_blocks(
    blocks: list[SubtitleBlock], options: SrtFormatOptions
) -> list[SubtitleBlock]:
    if not blocks:
        return []

    merged: list[SubtitleBlock] = [blocks[0]]
    for block in blocks[1:]:
        previous = merged[-1]
        merged_duration = max(previous.end, block.end) - previous.start
        if (
            block.start < previous.end
            and merged_duration <= options.max_overlapping_block_duration_s
            and len(previous.utterances) + len(block.utterances)
            <= options.max_utterances_per_block
            and _rendered_line_count(
                _line_count_utterance_preview(
                    [*previous.utterances, *block.utterances], options
                ),
                options,
            )
            <= options.max_lines_per_block
        ):
            previous.utterances.extend(block.utterances)
            previous.end = max(previous.end, block.end)
        else:
            merged.append(block)
    return merged


def _resolve_block_overlaps(
    blocks: list[SubtitleBlock], options: SrtFormatOptions
) -> None:
    for index in range(1, len(blocks)):
        previous = blocks[index - 1]
        current = blocks[index]
        if previous.end <= current.start:
            continue

        if current.start - previous.start >= options.min_segment_duration_s:
            previous.end = current.start
            continue

        current.start = previous.end
        if current.end <= current.start:
            current.end = current.start + options.min_segment_duration_s


def _inline_short_same_speaker_utterances(
    blocks: list[SubtitleBlock], options: SrtFormatOptions
) -> None:
    for block in blocks:
        if len(block.utterances) < 2:
            continue
        if len({utterance.speaker_id for utterance in block.utterances}) != 1:
            continue

        inlined: list[Utterance] = []
        for utterance in block.utterances:
            if inlined and _can_inline_same_speaker_utterance(
                inlined[-1], utterance, options
            ):
                inlined[-1].text = f"{inlined[-1].text} {utterance.text}"
                inlined[-1].end = max(inlined[-1].end, utterance.end)
            else:
                inlined.append(utterance)
        block.utterances = inlined


def _line_count_utterance_preview(
    utterances: list[Utterance], options: SrtFormatOptions
) -> list[Utterance]:
    if len({utterance.speaker_id for utterance in utterances}) != 1:
        return utterances
    return _inline_short_same_speaker_utterance_preview(utterances, options)


def _inline_short_same_speaker_utterance_preview(
    utterances: list[Utterance], options: SrtFormatOptions
) -> list[Utterance]:
    preview: list[Utterance] = []
    for utterance in utterances:
        copy = Utterance(
            speaker_id=utterance.speaker_id,
            start=utterance.start,
            end=utterance.end,
            text=utterance.text,
        )
        if preview and _can_inline_same_speaker_utterance(
            preview[-1], copy, options
        ):
            preview[-1].text = f"{preview[-1].text} {copy.text}"
            preview[-1].end = max(preview[-1].end, copy.end)
        else:
            preview.append(copy)
    return preview


def _can_inline_same_speaker_utterance(
    left: Utterance, right: Utterance, options: SrtFormatOptions
) -> bool:
    if left.speaker_id != right.speaker_id:
        return False
    if not (
        _is_short_inline_utterance(left, options)
        and _is_short_inline_utterance(right, options)
    ):
        return False
    gap = max(0.0, right.start - left.end)
    if gap > options.merge_same_speaker_gap_s:
        return False
    combined_text = f"{left.text} {right.text}"
    return len(combined_text) <= options.max_characters_per_line


def _is_short_inline_utterance(
    utterance: Utterance, options: SrtFormatOptions
) -> bool:
    text = utterance.text.strip()
    return (
        bool(text)
        and len(text) <= options.max_inline_short_utterance_chars
        and _ends_with_split_punctuation(text, options)
    )


def _can_merge_into_block(
    block: SubtitleBlock, utterance: Utterance, options: SrtFormatOptions
) -> bool:
    gap = utterance.start - block.end
    same_speaker = block.utterances[-1].speaker_id == utterance.speaker_id
    if same_speaker and _ends_with_split_punctuation(
        block.utterances[-1].text, options
    ):
        return False
    max_gap = (
        options.merge_same_speaker_gap_s
        if same_speaker
        else options.merge_speaker_turns_gap_s
    )
    if gap < 0:
        gap = 0
    if gap > max_gap:
        return False
    if len(block.utterances) + 1 > options.max_utterances_per_block:
        return False
    if (
        _rendered_line_count([*block.utterances, utterance], options)
        > options.max_lines_per_block
    ):
        return False
    if utterance.end - block.start > options.max_segment_duration_s:
        return False
    if _block_text_length(block) + len(utterance.text) > options.max_segment_chars:
        return False
    return True


def _render_srt(
    blocks: list[SubtitleBlock], options: SrtFormatOptions
) -> str:
    lines: list[str] = []
    for index, block in enumerate(blocks, start=1):
        lines.append(str(index))
        lines.append(f"{_format_time(block.start)} --> {_format_time(block.end)}")
        lines.extend(_render_block_text(block, options))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_block_text(
    block: SubtitleBlock, options: SrtFormatOptions
) -> list[str]:
    use_dialogue = (
        options.include_speaker_prefix_for_dialogue
        and len({item.speaker_id for item in block.utterances}) > 1
    )
    rendered: list[str] = []
    for utterance in block.utterances:
        text = utterance.text.strip()
        if not text:
            continue
        for line in _wrap_text(text, options.max_characters_per_line):
            if use_dialogue:
                rendered.append(f"{options.dialogue_prefix}{line}")
            else:
                rendered.append(line)
    return rendered


def _rendered_line_count(
    utterances: list[Utterance], options: SrtFormatOptions
) -> int:
    return sum(
        len(_wrap_text(utterance.text.strip(), options.max_characters_per_line))
        for utterance in utterances
        if utterance.text.strip()
    )


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    lines: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = _find_wrap_index(remaining, max_chars)
        lines.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        lines.append(remaining)
    return lines


def _find_wrap_index(text: str, max_chars: int) -> int:
    candidates = [
        text.rfind(punctuation, 0, max_chars + 1)
        for punctuation in JAPANESE_SOFT_PUNCTUATION + JAPANESE_HARD_PUNCTUATION
    ]
    best = max(candidates)
    if best >= max_chars // 2:
        return best + 1
    return max_chars


def _join_token_texts(
    tokens: list[WordToken], options: SrtFormatOptions
) -> str:
    text = ""
    for token in tokens:
        text = _join_text_parts(text, token.text, options)
    return _normalize_spacing(text)


def _join_text_parts(
    left: str, right: str, options: SrtFormatOptions
) -> str:
    if not left:
        return right
    if not right:
        return left
    if options.text_join_language == "ja":
        if right[0] in NO_SPACE_BEFORE or left[-1] in NO_SPACE_AFTER:
            return left + right
        if _needs_ascii_space(left[-1], right[0]):
            return left + " " + right
        return left + right
    return left + " " + right


def _normalize_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([。、，,.！？?!：:；;）)\]」』】》〉])", r"\1", text)
    text = re.sub(r"([（(\[「『【《〈])\s+", r"\1", text)
    return text.strip()


def _needs_ascii_space(left: str, right: str) -> bool:
    return bool(re.match(r"[A-Za-z0-9]", left) and re.match(r"[A-Za-z0-9]", right))


def _is_unsafe_segment_start(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return (
        stripped[0] in NO_SPACE_BEFORE
        or stripped in JAPANESE_UNSAFE_SEGMENT_STARTS
    )


def _ends_with_split_punctuation(
    text: str, options: SrtFormatOptions
) -> bool:
    return bool(text and text[-1] in options.split_on_punctuation)


def _ends_with_soft_split_punctuation(
    text: str, options: SrtFormatOptions
) -> bool:
    return bool(text and text[-1] in options.soft_split_punctuation)


def _block_text_length(block: SubtitleBlock) -> int:
    return sum(len(item.text) for item in block.utterances)


def _format_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
