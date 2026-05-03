"""Structural repair for chunk SRT outputs.

The source SRT is the only authority for final index/timecode metadata. The
translator output is treated as an immutable sequence of text payloads that may
have bad indices, bad timecodes, missing blocks, or extra blocks.

The repair strategy is deliberately layered:
1. Cheap local canonicalizers handle low-risk structural mistakes.
2. DeepSeek is used only when local metadata evidence is not enough.
3. Even DeepSeek may only return block assignments; local code still rebuilds
   the final SRT from the source skeleton and existing output text.
"""

import asyncio
import json
import re
from typing import Callable

from loguru import logger
from openai import AsyncOpenAI

from settings import settings
from services.gemini.errors import ChunkFixError
from services.gemini.chunker import SrtBlock, parse_srt, serialize_srt
from .instructions import chunk_fix_instruction

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHUNK_FIX_MODEL = "deepseek-v4-flash"
DEEPSEEK_TIMEOUT_SECONDS = 6 * 60
DEEPSEEK_PRICE_PER_1M_CACHE_HIT_INPUT = 0.0028
DEEPSEEK_PRICE_PER_1M_CACHE_MISS_INPUT = 0.14
DEEPSEEK_PRICE_PER_1M_OUTPUT = 0.28
_BLOCK_SEPARATOR = re.compile(r"\r?\n\r?\n")
# Lenient timecode pattern. The strict parser in chunker.py requires zero-padded
# fields; this lenient form accepts malformed-but-timecode-shaped lines so the
# lenient parser can strip them as metadata instead of preserving them as text.
_TIMECODE_LINE = re.compile(
    r"^\d{1,2}:\d{1,2}:\d{1,2}[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{1,2}:\d{1,2}[,.]\d{1,3}$"
)


class _ChunkFixCallError(RuntimeError):
    def __init__(self, message: str, accumulated_cost: float = 0.0):
        super().__init__(message)
        self.accumulated_cost = accumulated_cost


def _drain_cancelled_task(task: asyncio.Task) -> None:
    try:
        task.result()
    except (asyncio.CancelledError, Exception):
        pass


async def _await_with_manual_timeout(
    coro, timeout_seconds: float, operation: str
):
    task = asyncio.create_task(coro)
    done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
    if task in done:
        return task.result()

    task.cancel()
    task.add_done_callback(_drain_cancelled_task)
    raise TimeoutError(f"{operation} timed out after {timeout_seconds:g}s")


def _build_user_message(source_srt: str, broken_output: str, error: str) -> str:
    return (
        "下游譯者輸出的 SRT 結構與來源不符，請輸出 JSON 對位資訊。\n"
        "不要輸出 SRT，不要改寫、分割、合併任何譯文 text。\n\n"
        f"【驗證錯誤】\n{error}\n\n"
        f"【來源 SRT（權威 index/timecode）】\n---\n{source_srt}\n---\n\n"
        f"【待修復的翻譯 SRT】\n---\n{broken_output}\n---"
    )


def _parse_output_blocks_lenient(
    output_srt: str, start_index: int = 1
) -> list[SrtBlock]:
    """Parse broken model output while preserving text as much as possible.

    The normal SRT parser is intentionally strict and raises on malformed index
    or timecode lines. The fix layer needs a more tolerant view because broken
    output is exactly what it receives. This parser:
    - ignores the printed output index and replaces it with physical order;
    - accepts a valid timecode found in the first few lines;
    - preserves text lines without translating or normalizing them.

    `start_index` controls the physical-order numbering. The default of 1 is
    used by local canonicalizers that rebuild from source metadata anyway.
    The LLM-facing path passes the source SRT's first index so output indices
    share the same numeric range as source, making 1-to-1 mappings obvious.

    If no valid timecode exists, a dummy timecode is used only so the text can
    survive into later local/LLM assignment steps. The dummy timecode is never
    allowed into final output because final metadata always comes from source.
    """
    blocks: list[SrtBlock] = []
    for ordinal, raw_block in enumerate(
        _BLOCK_SEPARATOR.split(output_srt.strip()), start=start_index
    ):
        lines = raw_block.strip().splitlines()
        if not lines:
            continue

        timecode_line_index: int | None = None
        for index, line in enumerate(lines[:3]):
            if _TIMECODE_LINE.match(line.strip()):
                timecode_line_index = index
                break

        if timecode_line_index is None:
            text = "\n".join(lines)
            timecode = "00:00:00,000 --> 00:00:00,000"
        else:
            text = "\n".join(lines[timecode_line_index + 1 :])
            timecode = lines[timecode_line_index].strip()

        blocks.append(SrtBlock(index=ordinal, timecode=timecode, text=text))
    return blocks


def canonicalize_by_position(source_srt: str, output_srt: str) -> str | None:
    """Use physical order when source/output block counts already match.

    This handles common "metadata only" mistakes: shifted printed indices,
    wrong timecodes, or malformed index lines. It is safe only when the block
    counts match, because every output text can be paired with exactly one
    source block by position.
    """
    source_blocks = parse_srt(source_srt)
    output_blocks = _parse_output_blocks_lenient(output_srt)
    if len(source_blocks) != len(output_blocks):
        return None

    fixed_blocks = [
        SrtBlock(index=src.index, timecode=src.timecode, text=out.text)
        for src, out in zip(source_blocks, output_blocks)
    ]
    return serialize_srt(fixed_blocks)


def canonicalize_by_timecode_subset(
    source_srt: str, output_srt: str
) -> str | None:
    """Use exact timecode matches when output is a clean subset of source.

    If every output timecode exists in source and there are no duplicates, the
    text can be copied by timecode and missing source blocks can be represented
    as empty text. Any unexpected timecode makes this path unsafe because it
    would require guessing where that text belongs.
    """
    source_blocks = parse_srt(source_srt)
    output_blocks = parse_srt(output_srt)
    source_timecodes = {block.timecode for block in source_blocks}
    output_by_timecode: dict[str, SrtBlock] = {}

    for block in output_blocks:
        if block.timecode not in source_timecodes:
            return None
        if block.timecode in output_by_timecode:
            return None
        output_by_timecode[block.timecode] = block

    if len(output_by_timecode) == len(source_blocks):
        return None

    fixed_blocks = [
        SrtBlock(
            index=src.index,
            timecode=src.timecode,
            text=(
                output_by_timecode[src.timecode].text
                if src.timecode in output_by_timecode
                else ""
            ),
        )
        for src in source_blocks
    ]
    return serialize_srt(fixed_blocks)


def canonicalize_by_aligned_sequence(
    source_srt: str, output_srt: str
) -> str | None:
    """Use matching timecodes as anchors and fill only small local gaps.

    This is for outputs where most blocks still have correct source timecodes,
    but a small gap contains an unexpected timecode or missing source block.
    Matching timecodes become anchors. Between two anchors, output text is
    assigned to source blocks by order, and extra source blocks become empty.

    The heuristic is deliberately bounded by
    `settings.gemini_chunk_missing_block_tolerance`. Larger gaps are too
    ambiguous to guess locally and must fall through to LLM assignment.
    """
    source_blocks = parse_srt(source_srt)
    output_blocks = _parse_output_blocks_lenient(output_srt)
    source_by_timecode = {
        block.timecode: index for index, block in enumerate(source_blocks)
    }
    output_seen_timecodes: set[str] = set()
    anchors: list[tuple[int, int]] = []

    for output_index, block in enumerate(output_blocks):
        source_index = source_by_timecode.get(block.timecode)
        if source_index is None:
            continue
        if block.timecode in output_seen_timecodes:
            continue
        output_seen_timecodes.add(block.timecode)
        anchors.append((output_index, source_index))

    anchors = [
        anchor
        for index, anchor in enumerate(anchors)
        if index == 0 or anchor[1] > anchors[index - 1][1]
    ]
    if not anchors:
        return None

    text_by_source_position: dict[int, str] = {}
    previous_output = -1
    previous_source = -1
    max_gap_blocks = settings.gemini_chunk_missing_block_tolerance

    for next_output, next_source in anchors + [
        (len(output_blocks), len(source_blocks))
    ]:
        # Do not turn this local heuristic into broad subtitle alignment.
        # Small gaps are usually one-off metadata errors; large gaps need LLM
        # judgment because positional mapping becomes guesswork.
        gap_output_count = next_output - previous_output - 1
        gap_source_count = next_source - previous_source - 1
        if max(gap_output_count, gap_source_count) > max_gap_blocks:
            return None

        gap_outputs = output_blocks[previous_output + 1 : next_output]
        gap_source_positions = range(previous_source + 1, next_source)
        for source_position, output_block in zip(
            gap_source_positions, gap_outputs
        ):
            text_by_source_position[source_position] = output_block.text

        if next_output < len(output_blocks) and next_source < len(
            source_blocks
        ):
            text_by_source_position[next_source] = output_blocks[
                next_output
            ].text

        previous_output = next_output
        previous_source = next_source

    fixed_blocks = [
        SrtBlock(
            index=src.index,
            timecode=src.timecode,
            text=text_by_source_position.get(source_position, ""),
        )
        for source_position, src in enumerate(source_blocks)
    ]
    fixed_text = serialize_srt(fixed_blocks)
    if fixed_text == output_srt:
        return None
    return fixed_text


def _normalize_output_indices(output_srt: str, start_index: int) -> str:
    """Make output block indices match physical order before asking the LLM.

    The original printed output indices are often part of the bug, so the LLM
    should not reference them. Before each LLM retry, current broken output is
    rewritten with sequential indices starting at `start_index` (the source
    SRT's first index), so output and source share the same numeric range and
    trivial 1-to-1 mappings appear as `output_index == source_index`.
    """
    return serialize_srt(
        _parse_output_blocks_lenient(output_srt, start_index=start_index)
    )


def _apply_block_assignments(
    source_srt: str,
    output_srt: str,
    assignments: list[dict],
    output_start_index: int,
) -> str:
    """Apply LLM-provided metadata assignments without touching text.

    Assignments map normalized output block indices to authoritative source
    indices. `output_start_index` must match the value used when normalizing
    the output before the LLM call so the assignment lookup keys agree.
    Unassigned source blocks are intentionally emitted with empty text.
    Extra output blocks disappear. This keeps the LLM away from final SRT
    serialization and prevents it from rewriting translations.
    """
    source_blocks = parse_srt(source_srt)
    output_blocks = _parse_output_blocks_lenient(
        output_srt, start_index=output_start_index
    )
    source_by_index = {block.index: block for block in source_blocks}
    output_by_index = {block.index: block for block in output_blocks}
    text_by_source_index: dict[int, str] = {}

    for assignment in assignments:
        output_index = int(assignment["output_index"])
        source_index = int(assignment["source_index"])
        source_block = source_by_index.get(source_index)
        output_block = output_by_index.get(output_index)
        if source_block is None or output_block is None:
            raise ValueError(
                "Invalid block assignment "
                f"output_index={output_index}, source_index={source_index}"
            )
        if source_index in text_by_source_index:
            raise ValueError(
                f"Duplicate assignment for source index {source_index}"
            )
        text_by_source_index[source_index] = output_block.text

    fixed_blocks = [
        SrtBlock(
            index=src.index,
            timecode=src.timecode,
            text=text_by_source_index.get(src.index, ""),
        )
        for src in source_blocks
    ]
    return serialize_srt(fixed_blocks)


def _parse_assignment_response(text: str) -> list[dict]:
    """Validate the minimal JSON shape returned by DeepSeek."""
    payload = json.loads(text)
    assignments = payload.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("Fix response must contain an assignments array")
    for assignment in assignments:
        if not isinstance(assignment, dict):
            raise ValueError("Each assignment must be an object")
        if "output_index" not in assignment or "source_index" not in assignment:
            raise ValueError(
                "Each assignment must include output_index and source_index"
            )
    return assignments


def _get_usage_int(usage, field: str) -> int:
    value = getattr(usage, field, 0) or 0
    return int(value)


def _calculate_deepseek_cost(response, log_prefix: str) -> float:
    usage = getattr(response, "usage", None)
    if usage is None:
        logger.warning(f"{log_prefix} DeepSeek usage metadata is missing")
        return 0.0

    cache_hit_input_tokens = _get_usage_int(usage, "prompt_cache_hit_tokens")
    cache_miss_input_tokens = _get_usage_int(usage, "prompt_cache_miss_tokens")
    output_tokens = _get_usage_int(usage, "completion_tokens")
    prompt_tokens = _get_usage_int(usage, "prompt_tokens")
    total_tokens = _get_usage_int(usage, "total_tokens")

    completion_details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = (
        _get_usage_int(completion_details, "reasoning_tokens")
        if completion_details is not None
        else 0
    )

    cost_cache_hit = (
        cache_hit_input_tokens / 1_000_000
    ) * DEEPSEEK_PRICE_PER_1M_CACHE_HIT_INPUT
    cost_cache_miss = (
        cache_miss_input_tokens / 1_000_000
    ) * DEEPSEEK_PRICE_PER_1M_CACHE_MISS_INPUT
    cost_output = (output_tokens / 1_000_000) * DEEPSEEK_PRICE_PER_1M_OUTPUT
    total_cost = cost_cache_hit + cost_cache_miss + cost_output

    logger.info(f"{log_prefix} --- DeepSeek cost breakdown ---")
    logger.info(
        f"{log_prefix} Prompt tokens: {prompt_tokens} "
        f"(cache hit {cache_hit_input_tokens}, cache miss {cache_miss_input_tokens})"
    )
    logger.info(
        f"{log_prefix} Output tokens: {output_tokens} "
        f"(reasoning {reasoning_tokens}, total {total_tokens})"
    )
    logger.info(f"{log_prefix} DeepSeek fix cost: ${total_cost:.6f} USD")

    return total_cost


async def _call_once(
    source_srt: str,
    broken_output: str,
    error: str,
    reasoning_effort: str,
    log_prefix: str,
) -> tuple[str, float]:
    """Request one JSON assignment response from DeepSeek."""
    user_message = _build_user_message(source_srt, broken_output, error)
    logger.info(
        f"{log_prefix} Attempting structural fix via "
        f"{DEEPSEEK_CHUNK_FIX_MODEL} (effort={reasoning_effort})"
    )

    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=DEEPSEEK_BASE_URL,
    )

    response = await _await_with_manual_timeout(
        client.chat.completions.create(
            model=DEEPSEEK_CHUNK_FIX_MODEL,
            reasoning_effort=reasoning_effort,
            extra_body={"thinking": {"type": "enabled"}},
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": chunk_fix_instruction},
                {"role": "user", "content": user_message},
            ],
        ),
        DEEPSEEK_TIMEOUT_SECONDS,
        "Chunk fix DeepSeek call",
    )

    choice = response.choices[0]
    finish_reason = choice.finish_reason
    cost = _calculate_deepseek_cost(response, log_prefix)
    if finish_reason != "stop":
        raise _ChunkFixCallError(
            f"Fix non-stop finish reason: {finish_reason} (likely length)",
            accumulated_cost=cost,
        )

    text = choice.message.content or ""

    logger.info(f"{log_prefix} Fix call completed (${cost:.4f})")
    return text, cost


async def fix_chunk_structure(
    source_srt: str,
    broken_output: str,
    error: str,
    validate: Callable[[str], None],
    log_prefix: str = "",
) -> tuple[str, float]:
    """Repair broken chunk output through iterative assignment retries.

    `validate` must raise ValueError when the candidate text still fails
    structural validation; any other exception propagates. Accumulated cost
    across all attempts is returned alongside the first validated text.

    Retries up to settings.llm_chunk_fix_max_retries. Raises RuntimeError if
    all attempts exhaust. The LLM returns metadata assignments only; local code
    applies them onto the source SRT skeleton so translation text is never
    rewritten by the fix layer.

    On validation failure, the reconstructed candidate becomes the next
    `current_broken` input. This lets retries improve the remaining structural
    errors instead of starting from the original output each time.
    """
    max_retries = settings.llm_chunk_fix_max_retries
    total_cost = 0.0
    source_blocks_for_offset = parse_srt(source_srt)
    output_start_index = (
        source_blocks_for_offset[0].index if source_blocks_for_offset else 1
    )
    current_broken = _normalize_output_indices(broken_output, output_start_index)
    current_error = error
    reasoning_effort = "high"
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            text, cost = await _call_once(
                source_srt,
                current_broken,
                current_error,
                reasoning_effort,
                log_prefix,
            )
            total_cost += cost
            assignments = _parse_assignment_response(text)
            fixed_text = _apply_block_assignments(
                source_srt, current_broken, assignments, output_start_index
            )

            for assignment in assignments:
                logger.info(
                    f"{log_prefix} Assignment: {assignment['output_index']} -> {assignment['source_index']}"
                )

            logger.debug(
                f"{log_prefix} Fix assignment count: {len(assignments)}"
            )

            try:
                validate(fixed_text)
            except ValueError as validation_error:
                logger.warning(
                    f"{log_prefix} Fix attempt {attempt}/{max_retries} still "
                    f"invalid: {validation_error}"
                )
                current_broken = _normalize_output_indices(
                    fixed_text, output_start_index
                )
                current_error = str(validation_error)
                last_exception = validation_error
            else:
                return fixed_text, total_cost
        except Exception as e:
            if isinstance(e, _ChunkFixCallError):
                total_cost += e.accumulated_cost
            last_exception = e
            logger.warning(
                f"{log_prefix} Fix attempt {attempt}/{max_retries} errored: {e}"
            )

        if attempt < max_retries:
            await asyncio.sleep(2 ** (attempt - 1))

    raise ChunkFixError(
        f"Fix layer exhausted {max_retries} attempts; last error: {last_exception}",
        accumulated_cost=total_cost,
    ) from last_exception
