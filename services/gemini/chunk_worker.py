"""Translate a single SRT chunk concurrently with timecode-first validation."""

import asyncio
import hashlib
import json
from pathlib import Path

from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from services.llm.chunk_fix import fix_chunk_structure
from .chunker import SrtBlock, parse_srt
from .cost import calculate_cost
from .instructions import chunk_instruction
from .pre_pass import PrePassResult, SegmentSummary


class ChunkTranslationResult(BaseModel):
    blocks: list[SrtBlock]
    cost: float
    retries: int


def _raw_cache_path(
    cache_dir: Path, from_index: int, to_index: int, user_message: str
) -> Path:
    """Build the stage-1 (raw chunk output) cache path.

    Hash covers the full user_message (pre-pass briefing + SRT slice + chunk
    position), so any upstream change invalidates the cache automatically.
    Raw cache is written on any API response regardless of validation.
    """
    digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8]
    return cache_dir / f"chunk_{from_index:04d}-{to_index:04d}_{digest}.raw.srt"


def _fixed_cache_path(
    cache_dir: Path,
    from_index: int,
    to_index: int,
    user_message: str,
    raw_text: str,
) -> Path:
    """Build the stage-2 (post-fix) cache path.

    Keyed by (user_message, raw_text) so edits to raw cache or prompt force a
    re-fix, but untouched raw + fix-instruction combo reuses the prior result.
    """
    user_digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8]
    raw_digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:8]
    return (
        cache_dir
        / f"chunk_{from_index:04d}-{to_index:04d}_{user_digest}_{raw_digest}.fixed.srt"
    )


def _find_segment_summary(
    pre_pass: PrePassResult, from_index: int, to_index: int
) -> SegmentSummary | None:
    for s in pre_pass.segment_summaries:
        if s.from_index == from_index and s.to_index == to_index:
            return s
    return None


def _build_user_message(
    chunk: list[SrtBlock],
    chunk_index: int,
    total_chunks: int,
    pre_pass: PrePassResult,
) -> str:
    """Compose chunk-worker user message: briefing (global + local) + SRT slice."""
    from_index = chunk[0].index
    to_index = chunk[-1].index
    segment = _find_segment_summary(pre_pass, from_index, to_index)

    # Pre-pass briefing shared across chunks (everything except other chunks'
    # segment summaries) plus this chunk's own segment summary.
    briefing = {
        "summary": pre_pass.summary,
        "characters": [c.model_dump() for c in pre_pass.characters],
        "proper_nouns": pre_pass.proper_nouns,
        "glossary": pre_pass.glossary,
        "catchphrases": [c.model_dump() for c in pre_pass.catchphrases],
        "tone_notes": pre_pass.tone_notes,
        "segment_summary": segment.summary if segment else "",
    }

    srt_slice = "\n\n".join(b.raw for b in chunk)

    return (
        f"你是第 {chunk_index + 1}/{total_chunks} 塊翻譯員，負責 SRT index "
        f"{from_index}–{to_index}。請嚴格按照以下 pre-pass 簡報翻譯這段 SRT。\n\n"
        f"【Pre-pass 簡報】\n"
        f"{json.dumps(briefing, ensure_ascii=False, indent=2)}\n\n"
        f"【SRT 區段（index {from_index}–{to_index}，共 {len(chunk)} block）】\n"
        f"---\n{srt_slice}"
    )


def _validate_output(
    expected: list[SrtBlock], output_text: str
) -> list[SrtBlock]:
    """Parse output SRT and validate against input chunk by timecode.

    Index values from model output are ignored. We accept chunk outputs that
    keep all emitted timecodes on the source timeline and are missing no more
    than `settings.gemini_chunk_missing_block_tolerance` source blocks.

    Returned blocks are normalized onto the source chunk's index/timecode
    spine, then filtered to matched source blocks only.
    """
    parsed = parse_srt(output_text)
    errors: list[str] = []
    tolerance = settings.gemini_chunk_missing_block_tolerance

    expected_by_timecode = {block.timecode: block for block in expected}
    output_by_timecode: dict[str, SrtBlock] = {}
    duplicate_timecodes: set[str] = set()

    for out in parsed:
        if out.timecode not in expected_by_timecode:
            errors.append(
                f"Unexpected output timecode {out.timecode!r}"
            )
            continue
        if out.timecode in output_by_timecode:
            duplicate_timecodes.add(out.timecode)
            continue
        output_by_timecode[out.timecode] = out

    if duplicate_timecodes:
        dupes = ", ".join(repr(tc) for tc in sorted(duplicate_timecodes))
        errors.append(f"Duplicate output timecodes: {dupes}")

    missing = [
        src for src in expected if src.timecode not in output_by_timecode
    ]
    if len(missing) > tolerance:
        errors.append(
            f"Missing {len(missing)} source block(s) exceeds tolerance {tolerance}"
        )

    count_delta = len(expected) - len(parsed)
    if abs(count_delta) > tolerance:
        errors.append(
            f"Output block count delta {count_delta} exceeds tolerance {tolerance} "
            f"(output {len(parsed)} vs input {len(expected)})"
        )

    if errors:
        raise ValueError("; ".join(errors))

    normalized: list[SrtBlock] = []
    for src in expected:
        out = output_by_timecode.get(src.timecode)
        if out is None:
            continue
        normalized.append(
            SrtBlock(index=src.index, timecode=src.timecode, text=out.text)
        )
    return normalized


async def translate_chunk(
    client: genai.Client,
    audio_file: genai.types.File,
    chunk: list[SrtBlock],
    chunk_index: int,
    total_chunks: int,
    pre_pass: PrePassResult,
    cache_dir: Path,
) -> ChunkTranslationResult:
    """Translate one chunk with two-stage caching.

    Stage 1 (raw): Gemini's response is always written to the `.raw.srt`
    cache, regardless of structural validity. Chunk-level retries only cover
    API errors / MAX_TOKENS — validation failures do NOT trigger a chunk retry.

    Stage 2 (fixed): when raw fails validation, the fix layer retries on its
    own budget (settings.llm_chunk_fix_max_retries). A validated fix result is
    written to the `.fixed.srt` cache, keyed by raw text digest so an edited
    raw output or prompt change invalidates it.

    On load: prefer fixed cache → raw cache (validate / fix as needed) → API.
    Fix exhaustion raises without re-calling Gemini.
    """
    user_message = _build_user_message(
        chunk, chunk_index, total_chunks, pre_pass
    )
    thinking_level = genai.types.ThinkingLevel[settings.gemini_thinking_level]

    prefix = f"[chunk {chunk_index + 1}/{total_chunks}]"
    from_index = chunk[0].index
    to_index = chunk[-1].index
    raw_path = _raw_cache_path(cache_dir, from_index, to_index, user_message)
    source_srt = "\n\n".join(b.raw for b in chunk)

    raw_text: str | None = None
    api_cost = 0.0
    retries = 0

    if raw_path.exists():
        try:
            raw_text = raw_path.read_text(encoding="utf-8")
            logger.info(f"{prefix} Raw cache hit: {raw_path.name}")
        except OSError as e:
            logger.warning(
                f"{prefix} Raw cache read failed ({e}); calling API"
            )

    if raw_text is None:
        config = genai.types.GenerateContentConfig(
            system_instruction=chunk_instruction,
            safety_settings=[
                genai.types.SafetySetting(
                    category=genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                ),
                genai.types.SafetySetting(
                    category=genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                ),
                genai.types.SafetySetting(
                    category=genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                ),
                genai.types.SafetySetting(
                    category=genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=thinking_level
            ),
        )

        max_retries = settings.gemini_chunk_max_retries
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"{prefix} Translating index {from_index}–{to_index} "
                    f"({len(chunk)} blocks, attempt {attempt}/{max_retries})"
                )
                response = await client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=[audio_file, user_message],
                    config=config,
                )
                api_cost += calculate_cost(
                    response.usage_metadata, settings.gemini_model
                )

                finish_reason = (
                    response.candidates[0].finish_reason
                    if response.candidates
                    else None
                )
                if finish_reason != genai.types.FinishReason.STOP:
                    raise RuntimeError(
                        f"Non-STOP finish reason: {finish_reason} (likely MAX_TOKENS)"
                    )

                raw_text = response.text or ""
                retries = attempt - 1
                break
            except Exception as e:
                last_error = e
                logger.warning(f"{prefix} Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))

        if raw_text is None:
            logger.error(f"{prefix} All {max_retries} attempts failed")
            raise RuntimeError(
                f"Chunk {chunk_index + 1}/{total_chunks} failed after "
                f"{max_retries} attempts"
            ) from last_error

        try:
            raw_path.write_text(raw_text, encoding="utf-8")
        except OSError as e:
            logger.warning(
                f"{prefix} Failed to write raw cache {raw_path.name}: {e}"
            )

    fixed_path = _fixed_cache_path(
        cache_dir, from_index, to_index, user_message, raw_text
    )
    if fixed_path.exists():
        try:
            fixed_text = fixed_path.read_text(encoding="utf-8")
            blocks = _validate_output(chunk, fixed_text)
            logger.info(
                f"{prefix} Fixed cache hit: {len(blocks)} blocks from "
                f"{fixed_path.name}"
            )
            return ChunkTranslationResult(
                blocks=blocks, cost=api_cost, retries=retries
            )
        except (OSError, ValueError) as e:
            logger.warning(
                f"{prefix} Fixed cache unusable ({e}); re-running fix"
            )

    try:
        blocks = _validate_output(chunk, raw_text)
    except ValueError as validation_error:
        error_str = str(validation_error)
        logger.warning(
            f"{prefix} Raw output failed validation: {error_str}. "
            f"Running fix layer."
        )
    else:
        logger.success(
            f"{prefix} Completed {len(blocks)} blocks "
            f"(${api_cost:.4f}, retries={retries})"
        )
        return ChunkTranslationResult(
            blocks=blocks, cost=api_cost, retries=retries
        )

    def _validate(text: str) -> None:
        _validate_output(chunk, text)

    try:
        fixed_text, fix_cost = await fix_chunk_structure(
            source_srt, raw_text, error_str, _validate, prefix
        )
    except Exception as fix_error:
        raise RuntimeError(
            f"Fix layer failed ({fix_error}); original: {error_str}"
        ) from fix_error

    blocks = _validate_output(chunk, fixed_text)
    try:
        fixed_path.write_text(fixed_text, encoding="utf-8")
    except OSError as e:
        logger.warning(
            f"{prefix} Failed to write fixed cache {fixed_path.name}: {e}"
        )

    total_cost = api_cost + fix_cost
    logger.success(
        f"{prefix} Fix layer succeeded; {len(blocks)} blocks "
        f"(${total_cost:.4f}, retries={retries})"
    )
    return ChunkTranslationResult(
        blocks=blocks, cost=total_cost, retries=retries
    )
