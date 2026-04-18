"""Pre-pass analysis: scan full SRT once to produce a shared briefing for chunks."""

import asyncio
import json
from google import genai
from loguru import logger
from pydantic import BaseModel

from settings import settings
from .chunker import SrtBlock
from .cost import calculate_cost
from .instructions import pre_pass_instruction


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
    parts.append(f"\n【完整來源 SRT（ASR 產生，可能有錯）】\n---\n{srt_text}")
    return "\n".join(parts)


async def run_pre_pass(
    client: genai.Client,
    video_description: str | None,
    srt_text: str,
    chunks: list[list[SrtBlock]],
) -> tuple[PrePassResult, float]:
    """Run the single pre-pass call. Returns (parsed result, cost in USD).

    Retries up to gemini_chunk_max_retries on failure (schema parse or API error).
    Raises the last exception if all retries exhaust.
    """
    user_message = _build_user_message(video_description, srt_text, chunks)
    thinking_level = genai.types.ThinkingLevel[
        settings.gemini_pre_pass_thinking_level
    ]

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
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"[pre-pass] Requesting analysis (attempt {attempt}/{max_retries}, "
                f"thinking={settings.gemini_pre_pass_thinking_level})"
            )
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=user_message,
                config=config,
            )
            cost = calculate_cost(response.usage_metadata)
            result = PrePassResult.model_validate_json(response.text or "")
            logger.success(
                f"[pre-pass] Completed: {len(result.characters)} characters, "
                f"{len(result.proper_nouns)} proper_nouns, "
                f"{len(result.glossary)} glossary, "
                f"{len(result.catchphrases)} catchphrases, "
                f"{len(result.segment_summaries)} segment_summaries (${cost:.4f})"
            )
            return result, cost
        except Exception as e:
            last_error = e
            logger.warning(f"[pre-pass] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                await asyncio.sleep(backoff)

    logger.error(f"[pre-pass] All {max_retries} attempts failed")
    raise RuntimeError(
        f"Pre-pass failed after {max_retries} attempts"
    ) from last_error
