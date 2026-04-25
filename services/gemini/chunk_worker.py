"""Translate a single SRT chunk concurrently with timecode-first validation."""

import asyncio
import hashlib
import json

from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from services.llm.chunk_fix import fix_chunk_structure
from .assets import ChunkMediaAssets
from .chunker import SrtBlock, parse_srt
from .cost import calculate_cost
from .instructions import chunk_instruction
from .pre_pass import PrePassResult, SegmentSummary
from .storage import GeminiFileRef, GeminiStorage


class ChunkTranslationResult(BaseModel):
    blocks: list[SrtBlock]
    cost: float
    retries: int


def _raw_cache_path(
    response_dir, from_index: int, to_index: int, user_message: str
):
    digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8]
    return response_dir / f"chunk_{from_index:04d}-{to_index:04d}_{digest}.raw.srt"


def _fixed_cache_path(
    response_dir,
    from_index: int,
    to_index: int,
    user_message: str,
    raw_text: str,
):
    user_digest = hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8]
    raw_digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:8]
    return (
        response_dir
        / f"chunk_{from_index:04d}-{to_index:04d}_{user_digest}_{raw_digest}.fixed.srt"
    )


def _find_segment_summary(
    pre_pass: PrePassResult, from_index: int, to_index: int
) -> SegmentSummary | None:
    for segment in pre_pass.segment_summaries:
        if segment.from_index == from_index and segment.to_index == to_index:
            return segment
    return None


def _build_user_message(
    chunk: list[SrtBlock],
    chunk_index: int,
    total_chunks: int,
    pre_pass: PrePassResult,
    media_assets: ChunkMediaAssets,
) -> str:
    """Compose chunk-worker user message: briefing (global + local) + SRT slice."""
    from_index = chunk[0].index
    to_index = chunk[-1].index
    segment = _find_segment_summary(pre_pass, from_index, to_index)
    briefing = {
        "summary": pre_pass.summary,
        "characters": [c.model_dump() for c in pre_pass.characters],
        "proper_nouns": pre_pass.proper_nouns,
        "glossary": pre_pass.glossary,
        "catchphrases": [c.model_dump() for c in pre_pass.catchphrases],
        "tone_notes": pre_pass.tone_notes,
        "segment_summary": segment.summary if segment else "",
    }
    srt_slice = "\n\n".join(block.raw for block in chunk)
    frame_lines = "\n".join(
        [
            f"- {frame.timestamp_seconds:.3f}s"
            + (
                " (chunk 首幀)"
                if abs(
                    frame.timestamp_seconds
                    - media_assets.time_range.start_seconds
                )
                < 1e-6
                else ""
            )
            for frame in media_assets.frames
        ]
    )

    return (
        f"你是第 {chunk_index + 1}/{total_chunks} 塊翻譯員，負責 SRT index "
        f"{from_index}–{to_index}。\n\n"
        f"【Chunk 時間範圍】\n"
        f"{media_assets.time_range.start_seconds:.3f}s - "
        f"{media_assets.time_range.end_seconds:.3f}s\n\n"
        f"【Chunk 圖片時間點】\n"
        f"{frame_lines or '無'}\n\n"
        f"【Pre-pass 簡報】\n"
        f"{json.dumps(briefing, ensure_ascii=False, indent=2)}\n\n"
        f"【SRT 區段（index {from_index}–{to_index}，共 {len(chunk)} block）】\n"
        f"---\n{srt_slice}"
    )


def _validate_output(
    expected: list[SrtBlock], output_text: str
) -> list[SrtBlock]:
    """Parse output SRT and validate against input chunk by timecode."""
    parsed = parse_srt(output_text)
    errors: list[str] = []
    tolerance = settings.gemini_chunk_missing_block_tolerance

    expected_by_timecode = {block.timecode: block for block in expected}
    output_by_timecode: dict[str, SrtBlock] = {}
    duplicate_timecodes: set[str] = set()

    for out in parsed:
        if out.timecode not in expected_by_timecode:
            errors.append(f"Unexpected output timecode {out.timecode!r}")
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
    if missing and len(missing) <= tolerance:
        logger.warning(
            "Output missing {} source block(s) but within tolerance {}: {}",
            len(missing),
            tolerance,
            ", ".join(str(block.index) for block in missing),
        )
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


def _write_chunk_manifest(
    media_assets: ChunkMediaAssets,
    user_message: str,
    raw_path,
    fixed_path=None,
):
    try:
        manifest = {}
        if media_assets.manifest_path.exists():
            manifest = json.loads(
                media_assets.manifest_path.read_text(encoding="utf-8")
            )
        manifest.update(
            {
                "instruction_sha256": hashlib.sha256(
                    chunk_instruction.encode("utf-8")
                ).hexdigest(),
                "user_message_sha256": hashlib.sha256(
                    user_message.encode("utf-8")
                ).hexdigest(),
                "raw_response_path": str(raw_path),
                "fixed_response_path": str(fixed_path) if fixed_path else None,
            }
        )
        media_assets.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(
            f"Failed to update chunk manifest {media_assets.manifest_path}: {e}"
        )


async def translate_chunk(
    client: genai.Client,
    storage: GeminiStorage,
    media_assets: ChunkMediaAssets,
    chunk: list[SrtBlock],
    chunk_index: int,
    total_chunks: int,
    pre_pass: PrePassResult,
) -> ChunkTranslationResult:
    """Translate one chunk with persistent media cache and response caching."""
    user_message = _build_user_message(
        chunk, chunk_index, total_chunks, pre_pass, media_assets
    )
    thinking_level = genai.types.ThinkingLevel[settings.gemini_thinking_level]

    prefix = f"[chunk {chunk_index + 1}/{total_chunks}]"
    from_index = chunk[0].index
    to_index = chunk[-1].index
    raw_path = _raw_cache_path(
        media_assets.response_dir, from_index, to_index, user_message
    )
    source_srt = "\n\n".join(block.raw for block in chunk)

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
        gemini_inputs = storage.ensure_files(
            [
                media_assets.audio,
                *[
                    GeminiFileRef(
                        key=frame.storage_key,
                        file_path=frame.path,
                        mime_type=frame.mime_type,
                    )
                    for frame in media_assets.frames
                ],
            ]
        )

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"{prefix} Translating index {from_index}–{to_index} "
                    f"({len(chunk)} blocks, attempt {attempt}/{max_retries})"
                )
                response = await client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=[*gemini_inputs, user_message],
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
            _write_chunk_manifest(media_assets, user_message, raw_path)
        except OSError as e:
            logger.warning(
                f"{prefix} Failed to write raw cache {raw_path.name}: {e}"
            )

    fixed_path = _fixed_cache_path(
        media_assets.response_dir, from_index, to_index, user_message, raw_text
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
        _write_chunk_manifest(
            media_assets, user_message, raw_path, fixed_path=fixed_path
        )
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
