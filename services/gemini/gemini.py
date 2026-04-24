"""Gemini translation orchestrator: pre-pass + concurrent chunked translation."""

import asyncio
import shutil
import time
from pathlib import Path

from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from .chunk_worker import translate_chunk
from .chunker import SrtBlock, parse_srt, serialize_srt, split_into_chunks
from .pre_pass import PrePassResult, run_pre_pass


class TranslationResult(BaseModel):
    total_cost: float
    pre_pass_cost: float
    chunk_costs: list[float]
    num_chunks: int
    retries: int
    elapsed_seconds: float


class Gemini:
    """Google Gemini client for SRT subtitle translation.

    Flow: parse SRT → split into N char-balanced chunks → run one pre-pass
    analysis call → translate chunks concurrently (bounded by a semaphore) →
    validate index continuity → write output.
    """

    def __init__(self):
        logger.debug("Initializing Gemini client")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(
            f"Gemini client initialized "
            f"(concurrency={settings.gemini_concurrency}, "
            f"chunk_char_limit={settings.gemini_chunk_char_limit})"
        )

    def translate(
        self,
        video_description: str | None,
        srt_path: Path,
        output_path: Path,
        pre_pass_path: Path,
        chunks_cache_dir: Path,
    ) -> TranslationResult:
        """Translate an SRT file to Traditional Chinese. Blocks until complete.

        The pre-pass briefing is cached at pre_pass_path. If the file exists,
        the cached briefing is reused (skipping the pre-pass API call); this
        makes re-runs cheap when an earlier chunk translation failed.

        Per-chunk translations are cached in chunks_cache_dir during the run so
        that re-runs can skip chunks that already succeeded. The whole cache
        directory is deleted after the full translation completes.
        """
        return asyncio.run(
            self._translate_async(
                video_description,
                srt_path,
                output_path,
                pre_pass_path,
                chunks_cache_dir,
            )
        )

    async def _translate_async(
        self,
        video_description: str | None,
        srt_path: Path,
        output_path: Path,
        pre_pass_path: Path,
        chunks_cache_dir: Path,
    ) -> TranslationResult:
        start_time = time.time()
        logger.info(f"Starting translation for SRT file: {srt_path}")

        srt_text = srt_path.read_text(encoding="utf-8")
        blocks = parse_srt(srt_text)
        logger.info(f"Parsed {len(blocks)} SRT blocks")

        chunks = split_into_chunks(blocks, settings.gemini_chunk_char_limit)
        total_chars = sum(b.char_count for b in blocks)
        logger.info(
            f"Split into {len(chunks)} chunks "
            f"(total {total_chars} chars, avg {total_chars // max(1, len(chunks))} chars/chunk)"
        )
        for i, c in enumerate(chunks):
            logger.debug(
                f"  chunk {i + 1}/{len(chunks)}: index {c[0].index}–{c[-1].index} "
                f"({len(c)} blocks, {sum(b.char_count for b in c)} chars)"
            )

        if pre_pass_path.exists():
            logger.info(
                f"[pre-pass] Loading cached briefing from {pre_pass_path}"
            )
            pre_pass_result = PrePassResult.model_validate_json(
                pre_pass_path.read_text(encoding="utf-8")
            )
            pre_pass_cost = 0.0
        else:
            pre_pass_result, pre_pass_cost = await run_pre_pass(
                self.client, video_description, srt_text, chunks
            )
            pre_pass_path.parent.mkdir(parents=True, exist_ok=True)
            pre_pass_path.write_text(
                pre_pass_result.model_dump_json(indent=2),
                encoding="utf-8",
            )
            logger.info(f"[pre-pass] Saved briefing to {pre_pass_path}")

        chunks_cache_dir.mkdir(parents=True, exist_ok=True)
        semaphore = asyncio.Semaphore(settings.gemini_concurrency)

        async def bounded(i: int, chunk: list[SrtBlock]):
            async with semaphore:
                return await translate_chunk(
                    self.client,
                    chunk,
                    i,
                    len(chunks),
                    pre_pass_result,
                    chunks_cache_dir,
                )

        chunk_results = await asyncio.gather(
            *[bounded(i, c) for i, c in enumerate(chunks)]
        )

        # Merge and verify sequential index continuity across chunk boundaries.
        all_blocks: list[SrtBlock] = []
        for r in chunk_results:
            all_blocks.extend(r.blocks)
        for i in range(1, len(all_blocks)):
            prev = all_blocks[i - 1]
            curr = all_blocks[i]
            if curr.index != prev.index + 1:
                raise ValueError(
                    f"Index discontinuity at output position {i}: "
                    f"{prev.index} -> {curr.index}"
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialize_srt(all_blocks), encoding="utf-8")
        logger.success(f"Translation saved to: {output_path}")

        # One-shot chunk cache is only useful until the run succeeds; wipe it
        # so re-runs of a subsequent (new) translation don't inherit stale files.
        try:
            shutil.rmtree(chunks_cache_dir)
            logger.debug(f"Cleaned up chunk cache dir: {chunks_cache_dir}")
        except OSError as e:
            logger.warning(
                f"Failed to remove chunk cache dir {chunks_cache_dir}: {e}"
            )

        chunk_costs = [r.cost for r in chunk_results]
        total_retries = sum(r.retries for r in chunk_results)
        total_cost = pre_pass_cost + sum(chunk_costs)
        elapsed = time.time() - start_time

        logger.info(
            f"Translation done: {len(chunks)} chunks, {total_retries} retries, "
            f"${total_cost:.4f} (pre-pass ${pre_pass_cost:.4f}), "
            f"{elapsed:.1f}s ({elapsed / 60:.2f} min)"
        )

        return TranslationResult(
            total_cost=total_cost,
            pre_pass_cost=pre_pass_cost,
            chunk_costs=chunk_costs,
            num_chunks=len(chunks),
            retries=total_retries,
            elapsed_seconds=elapsed,
        )
