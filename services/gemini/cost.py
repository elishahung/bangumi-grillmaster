from pydantic import BaseModel
from google import genai
from loguru import logger
from settings import settings


class ModelCost(BaseModel):
    input: float
    cache_hit: float
    output: float


def calculate_cost(
    usage_metadata: genai.types.GenerateContentResponseUsageMetadata | None,
) -> float:
    if usage_metadata is None:
        logger.warning("Usage metadata is None")
        return 0.0

    pricing: dict[str, ModelCost] = {
        "gemini-3-flash-preview": ModelCost(
            input=0.50, cache_hit=0.10, output=3.00
        ),
        "gemini-3-pro-preview": ModelCost(
            input=2.00, cache_hit=0.20, output=12.00
        ),
    }

    model_name = settings.gemini_model
    if model_name not in pricing:
        logger.warning(f"Unknown model: {model_name}")
        return 0.0

    p = pricing[model_name]

    # 1. Get token counts (all fields are Optional, default to 0 if None)
    total_prompt = usage_metadata.prompt_token_count or 0
    cached_tokens = usage_metadata.cached_content_token_count or 0
    output_tokens = usage_metadata.candidates_token_count or 0
    thinking_tokens = usage_metadata.thoughts_token_count or 0

    # prompt_token_count includes cached tokens, so subtract to get actual input
    actual_input_tokens = total_prompt - cached_tokens

    # 2. Calculate costs (prices are per 1M tokens)
    # Thinking tokens are priced the same as output tokens
    cost_input = (actual_input_tokens / 1_000_000) * p.input
    cost_cache = (cached_tokens / 1_000_000) * p.cache_hit
    cost_output = (output_tokens / 1_000_000) * p.output
    cost_thinking = (thinking_tokens / 1_000_000) * p.output

    total_cost = cost_input + cost_cache + cost_output + cost_thinking

    logger.info(f"--- Cost breakdown ({model_name}) ---")
    logger.info(f"New input tokens: {actual_input_tokens} (${cost_input:.6f})")
    logger.info(f"Cache hit tokens: {cached_tokens} (${cost_cache:.6f})")
    logger.info(f"Output tokens: {output_tokens} (${cost_output:.6f})")
    logger.info(f"Thinking tokens: {thinking_tokens} (${cost_thinking:.6f})")
    logger.info(f"Total cost: ${total_cost:.6f} USD")

    return total_cost
