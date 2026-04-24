"""Translate a single SRT chunk concurrently. Strict index/timecode validation on output."""

import asyncio
import hashlib
import json
from pathlib import Path

from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from .chunker import SrtBlock, parse_srt
from .cost import calculate_cost
from .instructions import chunk_fix_instruction, chunk_instruction
from .pre_pass import PrePassResult, SegmentSummary


class ChunkTranslationResult(BaseModel):
    blocks: list[SrtBlock]
    cost: float
    retries: int


def _cache_path(
    cache_dir: Path, from_index: int, to_index: int, user_message: str
) -> Path:
    """Build the per-chunk cache file path.

    Hash covers the full user_message (pre-pass briefing + SRT slice + chunk
    position), so any upstream change invalidates the cache automatically.
    """
    digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8]
    return cache_dir / f"chunk_{from_index:04d}-{to_index:04d}_{digest}.srt"


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


def _build_fix_user_message(
    chunk: list[SrtBlock], broken_output: str, error: str
) -> str:
    """Compose repair-call user message: validation error + source SRT + broken output."""
    source_srt = "\n\n".join(b.raw for b in chunk)
    return (
        "下游譯者輸出的 SRT 結構與來源不符，請在不改動譯文內容的前提下修復對位。\n\n"
        f"【驗證錯誤】\n{error}\n\n"
        f"【來源 SRT（權威 index/timecode）】\n---\n{source_srt}\n---\n\n"
        f"【待修復的翻譯 SRT】\n---\n{broken_output}\n---"
    )


async def _fix_chunk_output(
    client: genai.Client,
    chunk: list[SrtBlock],
    broken_output: str,
    error: str,
    prefix: str,
) -> tuple[str, float]:
    """Single structural-repair call using the cheaper fix model.

    No audio, no retries, LOW thinking. Returns (repaired_text, cost). Raises
    on API error or non-STOP finish reason.
    """
    config = genai.types.GenerateContentConfig(
        system_instruction=chunk_fix_instruction,
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
            thinking_level=genai.types.ThinkingLevel.LOW
        ),
    )
    user_message = _build_fix_user_message(chunk, broken_output, error)
    logger.info(
        f"{prefix} Attempting structural fix via {settings.gemini_fix_model}"
    )
    response = await client.aio.models.generate_content(
        model=settings.gemini_fix_model,
        contents=[user_message],
        config=config,
    )
    cost = calculate_cost(response.usage_metadata, settings.gemini_fix_model)
    finish_reason = (
        response.candidates[0].finish_reason if response.candidates else None
    )
    if finish_reason != genai.types.FinishReason.STOP:
        raise RuntimeError(
            f"Fix non-STOP finish reason: {finish_reason} (likely MAX_TOKENS)"
        )
    return response.text or "", cost


def _validate_output(
    expected: list[SrtBlock], output_text: str
) -> list[SrtBlock]:
    """Parse output SRT and verify structural integrity against input chunk.

    Raises ValueError if block count, indices, or timecodes diverge.
    """
    parsed = parse_srt(output_text)
    if len(parsed) != len(expected):
        raise ValueError(
            f"Output block count {len(parsed)} != input {len(expected)}"
        )
    for i, (src, out) in enumerate(zip(expected, parsed)):
        if out.index != src.index:
            raise ValueError(
                f"Block {i}: output index {out.index} != source {src.index}"
            )
        if out.timecode != src.timecode:
            raise ValueError(
                f"Block {i} (index {src.index}): timecode mismatch "
                f"({out.timecode!r} != {src.timecode!r})"
            )
    return parsed


async def translate_chunk(
    client: genai.Client,
    audio_file: genai.types.File,
    chunk: list[SrtBlock],
    chunk_index: int,
    total_chunks: int,
    pre_pass: PrePassResult,
    cache_dir: Path,
) -> ChunkTranslationResult:
    """Translate one chunk with retry on MAX_TOKENS, API errors, or validation failure.

    Retries up to gemini_chunk_max_retries. Raises RuntimeError if all attempts
    exhaust.

    Cache hit (matching filename under cache_dir) short-circuits the API call
    and returns cost=0, retries=0. Cache miss or corrupt cache falls through
    to the live call; a successful translation is written back to the cache.
    """
    user_message = _build_user_message(
        chunk, chunk_index, total_chunks, pre_pass
    )
    thinking_level = genai.types.ThinkingLevel[
        settings.gemini_chunk_thinking_level
    ]

    prefix = f"[chunk {chunk_index + 1}/{total_chunks}]"
    from_index = chunk[0].index
    to_index = chunk[-1].index
    cache_file = _cache_path(cache_dir, from_index, to_index, user_message)

    if cache_file.exists():
        try:
            cached_blocks = _validate_output(
                chunk, cache_file.read_text(encoding="utf-8")
            )
            logger.info(
                f"{prefix} Cache hit: loaded {len(cached_blocks)} blocks "
                f"from {cache_file.name}"
            )
            return ChunkTranslationResult(
                blocks=cached_blocks, cost=0.0, retries=0
            )
        except (OSError, ValueError) as e:
            logger.warning(
                f"{prefix} Cache file {cache_file.name} unusable ({e}); "
                f"falling back to API call"
            )

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
    total_cost = 0.0
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
            total_cost += calculate_cost(
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

            output_text = response.text or ""
            try:
                blocks = _validate_output(chunk, output_text)
            except ValueError as validation_error:
                logger.warning(
                    f"{prefix} Validation failed on attempt {attempt}: "
                    f"{validation_error}. Trying fix layer."
                )
                try:
                    fixed_text, fix_cost = await _fix_chunk_output(
                        client,
                        chunk,
                        output_text,
                        str(validation_error),
                        prefix,
                    )
                    total_cost += fix_cost
                    blocks = _validate_output(chunk, fixed_text)
                    output_text = fixed_text
                    logger.success(f"{prefix} Fix layer succeeded")
                except Exception as fix_error:
                    raise RuntimeError(
                        f"Fix layer failed ({fix_error}); "
                        f"original: {validation_error}"
                    ) from fix_error
            try:
                cache_file.write_text(output_text, encoding="utf-8")
            except OSError as e:
                logger.warning(
                    f"{prefix} Failed to write cache {cache_file.name}: {e}"
                )
            logger.success(
                f"{prefix} Completed {len(blocks)} blocks "
                f"(${total_cost:.4f}, retries={attempt - 1})"
            )
            return ChunkTranslationResult(
                blocks=blocks, cost=total_cost, retries=attempt - 1
            )
        except Exception as e:
            last_error = e
            logger.warning(f"{prefix} Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                await asyncio.sleep(backoff)

    logger.error(f"{prefix} All {max_retries} attempts failed")
    raise RuntimeError(
        f"Chunk {chunk_index + 1}/{total_chunks} failed after {max_retries} attempts"
    ) from last_error
