import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

from services.gemini.errors import ChunkFixError
from services.llm import chunk_fix


class FakeAsyncOpenAI:
    response = None
    create_calls = []
    init_calls = []
    hang = False

    def __init__(self, **kwargs):
        self.init_calls.append(kwargs)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.hang:
            await asyncio.Event().wait()
        return self.response


def make_response(
    *,
    content: str = "fixed",
    finish_reason: str = "stop",
    cache_hit_tokens: int = 0,
    cache_miss_tokens: int = 0,
    completion_tokens: int = 0,
    reasoning_tokens: int = 0,
):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=cache_hit_tokens + cache_miss_tokens,
            prompt_cache_hit_tokens=cache_hit_tokens,
            prompt_cache_miss_tokens=cache_miss_tokens,
            completion_tokens=completion_tokens,
            total_tokens=cache_hit_tokens + cache_miss_tokens + completion_tokens,
            completion_tokens_details=SimpleNamespace(
                reasoning_tokens=reasoning_tokens
            ),
        ),
    )


class ChunkFixTimeoutTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeAsyncOpenAI.response = None
        FakeAsyncOpenAI.create_calls = []
        FakeAsyncOpenAI.init_calls = []
        FakeAsyncOpenAI.hang = False

    async def test_fix_chunk_structure_times_out_hung_deepseek_call(self):
        FakeAsyncOpenAI.hang = True
        with (
            patch.object(chunk_fix, "AsyncOpenAI", FakeAsyncOpenAI),
            patch.object(chunk_fix, "DEEPSEEK_TIMEOUT_SECONDS", 0.01),
            patch.object(chunk_fix.settings, "llm_chunk_fix_max_retries", 1),
            patch.object(chunk_fix.settings, "deepseek_api_key", "test-key"),
        ):
            with self.assertRaises(ChunkFixError) as raised:
                await chunk_fix.fix_chunk_structure(
                    "1\n00:00:00,000 --> 00:00:01,000\nsource",
                    "broken",
                    "invalid structure",
                    lambda _text: None,
                    "[test]",
                )

        self.assertEqual(raised.exception.accumulated_cost, 0.0)
        self.assertIn("timed out", str(raised.exception))

    async def test_fix_chunk_structure_uses_deepseek_with_max_effort_and_cost(self):
        FakeAsyncOpenAI.response = make_response(
            content="fixed",
            cache_hit_tokens=1000,
            cache_miss_tokens=2000,
            completion_tokens=3000,
            reasoning_tokens=400,
        )

        with (
            patch.object(chunk_fix, "AsyncOpenAI", FakeAsyncOpenAI),
            patch.object(chunk_fix.settings, "llm_chunk_fix_max_retries", 1),
            patch.object(chunk_fix.settings, "deepseek_api_key", "test-key"),
        ):
            text, cost = await chunk_fix.fix_chunk_structure(
                "1\n00:00:00,000 --> 00:00:01,000\nsource",
                "broken",
                "invalid structure",
                lambda _text: None,
                "[test]",
            )

        self.assertEqual(text, "fixed")
        self.assertEqual(
            FakeAsyncOpenAI.init_calls[0],
            {
                "api_key": "test-key",
                "base_url": "https://api.deepseek.com",
            },
        )
        create_call = FakeAsyncOpenAI.create_calls[0]
        self.assertEqual(create_call["model"], "deepseek-v4-flash")
        self.assertEqual(create_call["reasoning_effort"], "max")
        self.assertEqual(
            create_call["extra_body"], {"thinking": {"type": "enabled"}}
        )
        expected_cost = (
            (1000 / 1_000_000) * 0.0028
            + (2000 / 1_000_000) * 0.14
            + (3000 / 1_000_000) * 0.28
        )
        self.assertAlmostEqual(cost, expected_cost)

    async def test_non_stop_finish_reason_preserves_accumulated_cost(self):
        FakeAsyncOpenAI.response = make_response(
            finish_reason="length",
            cache_hit_tokens=1000,
            cache_miss_tokens=2000,
            completion_tokens=3000,
        )

        with (
            patch.object(chunk_fix, "AsyncOpenAI", FakeAsyncOpenAI),
            patch.object(chunk_fix.settings, "llm_chunk_fix_max_retries", 1),
            patch.object(chunk_fix.settings, "deepseek_api_key", "test-key"),
        ):
            with self.assertRaises(ChunkFixError) as raised:
                await chunk_fix.fix_chunk_structure(
                    "1\n00:00:00,000 --> 00:00:01,000\nsource",
                    "broken",
                    "invalid structure",
                    lambda _text: None,
                    "[test]",
                )

        expected_cost = (
            (1000 / 1_000_000) * 0.0028
            + (2000 / 1_000_000) * 0.14
            + (3000 / 1_000_000) * 0.28
        )
        self.assertAlmostEqual(raised.exception.accumulated_cost, expected_cost)
        self.assertIn("non-stop finish reason: length", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
