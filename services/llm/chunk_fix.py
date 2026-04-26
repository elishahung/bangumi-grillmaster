"""Structural repair for chunk SRT outputs via DeepSeek.

Given a source SRT slice (authoritative index/timecode) and a broken translator
output, call an LLM to re-align blocks without changing translation wording.
"""

import asyncio
from typing import Callable

from loguru import logger
from openai import AsyncOpenAI

from settings import settings
from services.gemini.errors import ChunkFixError
from .instructions import chunk_fix_instruction

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHUNK_FIX_MODEL = "deepseek-v4-flash"
DEEPSEEK_TIMEOUT_SECONDS = 6 * 60
DEEPSEEK_PRICE_PER_1M_CACHE_HIT_INPUT = 0.0028
DEEPSEEK_PRICE_PER_1M_CACHE_MISS_INPUT = 0.14
DEEPSEEK_PRICE_PER_1M_OUTPUT = 0.28


class _ChunkFixCallError(RuntimeError):
    def __init__(self, message: str, accumulated_cost: float = 0.0):
        super().__init__(message)
        self.accumulated_cost = accumulated_cost


def _drain_cancelled_task(task: asyncio.Task) -> None:
    try:
        task.result()
    except (asyncio.CancelledError, Exception):
        pass


async def _await_with_manual_timeout(coro, timeout_seconds: float, operation: str):
    task = asyncio.create_task(coro)
    done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
    if task in done:
        return task.result()

    task.cancel()
    task.add_done_callback(_drain_cancelled_task)
    raise TimeoutError(f"{operation} timed out after {timeout_seconds:g}s")


def _build_user_message(source_srt: str, broken_output: str, error: str) -> str:
    return (
        "下游譯者輸出的 SRT 結構與來源不符，請在不改動譯文內容的前提下修復對位。\n\n"
        f"【驗證錯誤】\n{error}\n\n"
        f"【來源 SRT（權威 index/timecode）】\n---\n{source_srt}\n---\n\n"
        f"【待修復的翻譯 SRT】\n---\n{broken_output}\n---"
    )


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
    source_srt: str, broken_output: str, error: str, log_prefix: str
) -> tuple[str, float]:
    """Single repair call. Raises RuntimeError on non-stop finish reason."""
    user_message = _build_user_message(source_srt, broken_output, error)
    logger.info(
        f"{log_prefix} Attempting structural fix via {DEEPSEEK_CHUNK_FIX_MODEL}"
    )

    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=DEEPSEEK_BASE_URL,
    )

    response = await _await_with_manual_timeout(
        client.chat.completions.create(
            model=DEEPSEEK_CHUNK_FIX_MODEL,
            reasoning_effort="max",
            extra_body={"thinking": {"type": "enabled"}},
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
    """Repair broken chunk output, retrying until validate() passes.

    `validate` must raise ValueError when the candidate text still fails
    structural validation; any other exception propagates. Accumulated cost
    across all attempts is returned alongside the first validated text.

    Retries up to settings.llm_chunk_fix_max_retries. Raises RuntimeError if
    all attempts exhaust. The latest candidate text + validation error feed
    into the next attempt so the fix model can iterate on its own output.
    """
    max_retries = settings.llm_chunk_fix_max_retries
    total_cost = 0.0
    current_broken = broken_output
    current_error = error
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            text, cost = await _call_once(
                source_srt, current_broken, current_error, log_prefix
            )
            total_cost += cost
            try:
                validate(text)
            except ValueError as validation_error:
                logger.warning(
                    f"{log_prefix} Fix attempt {attempt}/{max_retries} still "
                    f"invalid: {validation_error}"
                )
                current_broken = text
                current_error = str(validation_error)
                last_exception = validation_error
            else:
                return text, total_cost
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
