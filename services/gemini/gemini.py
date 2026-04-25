"""Gemini translation orchestrator: pre-pass + concurrent chunked translation."""

import asyncio
import time
from pathlib import Path

from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from .assets import prepare_chunk_media_assets
from .chunk_worker import translate_chunk
from .chunker import SrtBlock, parse_srt, serialize_srt, split_into_chunks
from .pre_pass import run_pre_pass
from .storage import GeminiStorage


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
    normalize merged indices → write output.
    """

    def __init__(self):
        logger.debug("Initializing Gemini client")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.storage = GeminiStorage(self.client)
        logger.info(
            f"Gemini client initialized "
            f"(concurrency={settings.gemini_concurrency}, "
            f"chunk_char_limit={settings.gemini_chunk_char_limit})"
        )

    def translate(
        self,
        video_description: str | None,
        srt_path: Path,
        audio_key: str,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        pre_pass_path: Path,
        pre_pass_cache_dir: Path,
        chunks_cache_dir: Path,
    ) -> TranslationResult:
        """Translate an SRT file to Traditional Chinese. Blocks until complete.

        Pre-pass and per-chunk multimodal assets are cached on disk so a later
        retry can resume without rebuilding media slices or re-uploading files.
        """
        return asyncio.run(
            self._translate_async(
                video_description,
                srt_path,
                audio_key,
                video_path,
                audio_path,
                output_path,
                pre_pass_path,
                pre_pass_cache_dir,
                chunks_cache_dir,
            )
        )

    async def _translate_async(
        self,
        video_description: str | None,
        srt_path: Path,
        audio_key: str,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        pre_pass_path: Path,
        pre_pass_cache_dir: Path,
        chunks_cache_dir: Path,
    ) -> TranslationResult:
        start_time = time.time()
        logger.info(f"Starting translation for SRT file: {srt_path}")

        srt_text = srt_path.read_text(encoding="utf-8")
        audio_file = self.storage.ensure_file(
            audio_key, audio_path, "audio/ogg"
        )
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

        pre_pass_result, pre_pass_cost = await run_pre_pass(
            self.client,
            self.storage,
            video_description,
            srt_text,
            video_path,
            audio_key,
            audio_file,
            chunks,
            pre_pass_path,
            pre_pass_cache_dir,
        )

        chunks_cache_dir.mkdir(parents=True, exist_ok=True)
        semaphore = asyncio.Semaphore(settings.gemini_concurrency)

        async def bounded(i: int, chunk: list[SrtBlock]):
            async with semaphore:
                chunk_assets = prepare_chunk_media_assets(
                    video_path=video_path,
                    audio_path=audio_path,
                    cache_root=chunks_cache_dir,
                    video_key=audio_key,
                    chunk=chunk,
                    chunk_index=i,
                    total_chunks=len(chunks),
                    interval_seconds=settings.gemini_chunk_frame_interval_seconds,
                    max_side=settings.gemini_chunk_frame_max_side,
                    is_last_chunk=i == len(chunks) - 1,
                )
                return await translate_chunk(
                    self.client,
                    self.storage,
                    chunk_assets,
                    chunk,
                    i,
                    len(chunks),
                    pre_pass_result,
                )

        chunk_results = await asyncio.gather(
            *[bounded(i, c) for i, c in enumerate(chunks)]
        )

        # Merge chunk outputs, then rebuild contiguous SRT indices because
        # chunk validation may tolerate a small number of dropped blocks.
        all_blocks: list[SrtBlock] = []
        for r in chunk_results:
            all_blocks.extend(r.blocks)
        all_blocks = [
            SrtBlock(index=i, timecode=block.timecode, text=block.text)
            for i, block in enumerate(all_blocks, start=1)
        ]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialize_srt(all_blocks), encoding="utf-8")
        logger.success(f"Translation saved to: {output_path}")

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
