"""Pre-pass analysis: scan full SRT once to produce a shared briefing for chunks."""

import asyncio
import json
import hashlib
from pathlib import Path
from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from .assets import prepare_pre_pass_media_assets
from .chunker import SrtBlock
from .cost import calculate_cost
from .errors import PrePassError
from .instructions import pre_pass_instruction
from .storage import GeminiFileRef, GeminiStorage


class Character(BaseModel):
    name_jp: str
    name_zh: str
    role_note: str


class Catchphrase(BaseModel):
    phrase_jp: str
    phrase_zh: str
    note: str


class SegmentSummary(BaseModel):
    from_index: int
    to_index: int
    summary: str


class PrePassResult(BaseModel):
    summary: str
    characters: list[Character]
    proper_nouns: dict[str, str]
    glossary: dict[str, str]
    catchphrases: list[Catchphrase]
    tone_notes: str
    segment_summaries: list[SegmentSummary]


def _build_user_message(
    video_description: str | None,
    srt_text: str,
    chunks: list[list[SrtBlock]],
    frame_timestamps: list[float],
) -> str:
    """Compose the pre-pass user message with hint, chunk ranges, and full SRT."""
    boundaries = [
        {"from_index": c[0].index, "to_index": c[-1].index} for c in chunks
    ]
    parts = ["請分析以下日本綜藝節目字幕，輸出符合 schema 的 JSON 簡報。"]
    if video_description:
        parts.append(f"\n【節目標題/資訊】\n{video_description}")
    parts.append(
        "\n【Chunk 邊界】下游會將字幕切成以下 index 區間平行翻譯，請為每段輸出一個 segment_summary："
        f"\n{json.dumps(boundaries, ensure_ascii=False)}"
    )
    if frame_timestamps:
        parts.append(
            "\n【代表圖片時間點（秒）】\n"
            + ", ".join(f"{timestamp:.3f}" for timestamp in frame_timestamps)
        )
    parts.append(f"\n【完整來源 SRT（ASR 產生，可能有錯）】\n---\n{srt_text}")
    return "\n".join(parts)


async def run_pre_pass(
    client: genai.Client,
    storage: GeminiStorage,
    video_description: str | None,
    srt_text: str,
    video_path: Path,
    audio_key: str,
    audio_file: genai.types.File,
    chunks: list[list[SrtBlock]],
    pre_pass_path: Path,
    pre_pass_cache_dir: Path,
) -> tuple[PrePassResult, float]:
    """Run the single pre-pass call. Returns (parsed result, cost in USD).

    Retries up to gemini_chunk_max_retries on failure (schema parse or API error).
    Raises the last exception if all retries exhaust.
    """
    pre_pass_assets = prepare_pre_pass_media_assets(
        video_path=video_path,
        cache_root=pre_pass_cache_dir,
        video_key=audio_key,
        max_frames=settings.gemini_pre_pass_max_frames,
        max_side=settings.gemini_pre_pass_frame_max_side,
    )
    frame_timestamps = [
        frame.timestamp_seconds for frame in pre_pass_assets.frames
    ]
    user_message = _build_user_message(
        video_description, srt_text, chunks, frame_timestamps
    )
    thinking_level = genai.types.ThinkingLevel[settings.gemini_thinking_level]
    prompt_digest = hashlib.sha256(
        (
            pre_pass_instruction
            + user_message
            + str(settings.gemini_pre_pass_max_frames)
            + str(settings.gemini_pre_pass_frame_max_side)
        ).encode("utf-8")
    ).hexdigest()
    manifest_path = pre_pass_cache_dir / "manifest.json"

    if pre_pass_path.exists() and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("prompt_digest") == prompt_digest:
                logger.info(
                    f"[pre-pass] Cache validated by manifest {manifest_path}"
                )
                return (
                    PrePassResult.model_validate_json(
                        pre_pass_path.read_text(encoding="utf-8")
                    ),
                    0.0,
                )
        except Exception as e:
            logger.warning(f"[pre-pass] Manifest read failed: {e}")

    config = genai.types.GenerateContentConfig(
        system_instruction=pre_pass_instruction,
        response_mime_type="application/json",
        response_json_schema=PrePassResult.model_json_schema(),
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
    total_cost = 0.0
    for attempt in range(1, max_retries + 1):
        try:
            frame_files = await storage.ensure_files(
                [
                    GeminiFileRef(
                        key=frame.storage_key,
                        file_path=frame.path,
                        mime_type=frame.mime_type,
                    )
                    for frame in pre_pass_assets.frames
                ]
            )
            logger.info(
                f"[pre-pass] Requesting analysis (attempt {attempt}/{max_retries}, "
                f"thinking={settings.gemini_thinking_level})"
            )
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=[
                    audio_file,
                    *frame_files,
                    user_message,
                ],
                config=config,
            )
            cost = calculate_cost(
                response.usage_metadata, settings.gemini_model
            )
            total_cost += cost
            result = PrePassResult.model_validate_json(response.text or "")
            pre_pass_path.parent.mkdir(parents=True, exist_ok=True)
            pre_pass_path.write_text(
                result.model_dump_json(indent=2),
                encoding="utf-8",
            )
            pre_pass_cache_dir.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "prompt_digest": prompt_digest,
                        "instruction_sha256": hashlib.sha256(
                            pre_pass_instruction.encode("utf-8")
                        ).hexdigest(),
                        "user_message_sha256": hashlib.sha256(
                            user_message.encode("utf-8")
                        ).hexdigest(),
                        "frames": [
                            frame.model_dump(mode="json")
                            for frame in pre_pass_assets.frames
                        ],
                        "asset_manifest_path": str(
                            pre_pass_assets.manifest_path
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            logger.success(
                f"[pre-pass] Completed: {len(result.characters)} characters, "
                f"{len(result.proper_nouns)} proper_nouns, "
                f"{len(result.glossary)} glossary, "
                f"{len(result.catchphrases)} catchphrases, "
                f"{len(result.segment_summaries)} segment_summaries (${cost:.4f})"
            )
            return result, total_cost
        except Exception as e:
            last_error = e
            logger.warning(f"[pre-pass] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                await asyncio.sleep(backoff)

    logger.error(f"[pre-pass] All {max_retries} attempts failed")
    raise PrePassError(
        f"Pre-pass failed after {max_retries} attempts",
        accumulated_cost=total_cost,
    ) from last_error
