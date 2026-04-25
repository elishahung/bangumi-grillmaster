"""Structural repair for chunk SRT outputs via any litellm-supported provider.

Given a source SRT slice (authoritative index/timecode) and a broken translator
output, call an LLM to re-align blocks without changing translation wording.
"""

import asyncio
from typing import Callable

from litellm import acompletion, completion_cost
from loguru import logger

from settings import settings
from services.gemini.errors import ChunkFixError
from .instructions import chunk_fix_instruction

LITELLM_TIMEOUT_SECONDS = 6 * 60


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


async def _call_once(
    source_srt: str, broken_output: str, error: str, log_prefix: str
) -> tuple[str, float]:
    """Single repair call. Raises RuntimeError on non-stop finish reason."""
    model = settings.llm_chunk_fix_model
    user_message = _build_user_message(source_srt, broken_output, error)
    logger.info(f"{log_prefix} Attempting structural fix via {model}")

    response = await _await_with_manual_timeout(
        acompletion(
            model=model,
            api_key=settings.llm_api_key,
            timeout=LITELLM_TIMEOUT_SECONDS,
            messages=[
                {"role": "system", "content": chunk_fix_instruction},
                {"role": "user", "content": user_message},
            ],
        ),
        LITELLM_TIMEOUT_SECONDS,
        "Chunk fix litellm call",
    )

    choice = response.choices[0]
    finish_reason = choice.finish_reason
    if finish_reason != "stop":
        raise RuntimeError(
            f"Fix non-stop finish reason: {finish_reason} (likely length)"
        )

    text = choice.message.content or ""

    try:
        cost = float(completion_cost(completion_response=response) or 0.0)
    except Exception as e:
        logger.warning(f"{log_prefix} Failed to compute fix cost: {e}")
        cost = 0.0

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
