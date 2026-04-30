import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

from services.gemini.errors import ChunkFixError
from services.gemini.chunk_worker import _validate_output
from services.gemini.chunker import SrtBlock
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


class ChunkFixTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_fix_chunk_structure_uses_deepseek_with_high_effort_and_cost(self):
        FakeAsyncOpenAI.response = make_response(
            content='{"assignments":[{"output_index":1,"source_index":1}]}',
            cache_hit_tokens=1000,
            cache_miss_tokens=2000,
            completion_tokens=3000,
            reasoning_tokens=400,
        )
        validate_calls = []

        def validate(text: str) -> None:
            validate_calls.append(text)

        with (
            patch.object(chunk_fix, "AsyncOpenAI", FakeAsyncOpenAI),
            patch.object(chunk_fix.settings, "llm_chunk_fix_max_retries", 1),
            patch.object(chunk_fix.settings, "deepseek_api_key", "test-key"),
        ):
            text, cost = await chunk_fix.fix_chunk_structure(
                "1\n00:00:00,000 --> 00:00:01,000\nsource",
                "7\n00:00:09,000 --> 00:00:10,000\ntranslated",
                "invalid structure",
                validate,
                "[test]",
            )

        self.assertEqual(
            text,
            "1\n00:00:00,000 --> 00:00:01,000\ntranslated\n",
        )
        self.assertEqual(validate_calls, [text])
        self.assertEqual(
            FakeAsyncOpenAI.init_calls[0],
            {
                "api_key": "test-key",
                "base_url": "https://api.deepseek.com",
            },
        )
        create_call = FakeAsyncOpenAI.create_calls[0]
        self.assertEqual(create_call["model"], "deepseek-v4-flash")
        self.assertEqual(create_call["reasoning_effort"], "high")
        self.assertEqual(
            create_call["extra_body"], {"thinking": {"type": "enabled"}}
        )
        self.assertEqual(create_call["response_format"], {"type": "json_object"})
        first_user_message = create_call["messages"][1]["content"]
        self.assertIn(
            "1\n00:00:09,000 --> 00:00:10,000\ntranslated",
            first_user_message,
        )
        self.assertNotIn("7\n00:00:09,000 --> 00:00:10,000", first_user_message)
        expected_cost = (
            (1000 / 1_000_000) * 0.0028
            + (2000 / 1_000_000) * 0.14
            + (3000 / 1_000_000) * 0.28
        )
        self.assertAlmostEqual(cost, expected_cost)

    async def test_validation_failure_retries_with_high_effort(self):
        responses = [
            make_response(
                content='{"assignments":[{"output_index":1,"source_index":2}]}',
                cache_miss_tokens=1000,
                completion_tokens=1000,
            ),
            make_response(
                content='{"assignments":[{"output_index":2,"source_index":1}]}',
                cache_miss_tokens=2000,
                completion_tokens=2000,
            ),
        ]

        async def create_with_responses(self, **kwargs):
            self.create_calls.append(kwargs)
            return responses.pop(0)

        validate_calls = []

        def validate(text: str) -> None:
            validate_calls.append(text)
            if not text.startswith(
                "1\n00:00:00,000 --> 00:00:01,000\ntranslated"
            ):
                raise ValueError("still invalid")

        with (
            patch.object(chunk_fix, "AsyncOpenAI", FakeAsyncOpenAI),
            patch.object(FakeAsyncOpenAI, "_create", create_with_responses),
            patch.object(chunk_fix.settings, "llm_chunk_fix_max_retries", 2),
            patch.object(chunk_fix.settings, "deepseek_api_key", "test-key"),
            patch("services.llm.chunk_fix.asyncio.sleep", return_value=None),
        ):
            text, cost = await chunk_fix.fix_chunk_structure(
                (
                    "1\n00:00:00,000 --> 00:00:01,000\nsource 1\n\n"
                    "2\n00:00:02,000 --> 00:00:03,000\nsource 2"
                ),
                "1\n00:00:09,000 --> 00:00:10,000\ntranslated",
                "invalid structure",
                validate,
                "[test]",
            )

        self.assertEqual(
            text,
            (
                "1\n00:00:00,000 --> 00:00:01,000\ntranslated\n\n"
                "2\n00:00:02,000 --> 00:00:03,000\n\n"
            ),
        )
        self.assertEqual(
            validate_calls,
            [
                (
                    "1\n00:00:00,000 --> 00:00:01,000\n\n\n"
                    "2\n00:00:02,000 --> 00:00:03,000\ntranslated\n"
                ),
                (
                    "1\n00:00:00,000 --> 00:00:01,000\ntranslated\n\n"
                    "2\n00:00:02,000 --> 00:00:03,000\n\n"
                ),
            ],
        )
        self.assertEqual(
            [call["reasoning_effort"] for call in FakeAsyncOpenAI.create_calls],
            ["high", "high"],
        )
        second_user_message = FakeAsyncOpenAI.create_calls[1]["messages"][1][
            "content"
        ]
        self.assertIn("still invalid", second_user_message)
        self.assertIn(
            "2\n00:00:02,000 --> 00:00:03,000\ntranslated",
            second_user_message,
        )
        self.assertNotIn("00:00:09,000 --> 00:00:10,000", second_user_message)
        expected_cost = (
            (1000 / 1_000_000) * 0.14
            + (1000 / 1_000_000) * 0.28
            + (2000 / 1_000_000) * 0.14
            + (2000 / 1_000_000) * 0.28
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

    async def test_canonicalize_by_position_preserves_text_and_source_metadata(self):
        fixed = chunk_fix.canonicalize_by_position(
            (
                "10\n00:00:01,000 --> 00:00:02,000\nsource a\n\n"
                "11\n00:00:03,000 --> 00:00:04,000\nsource b\n"
            ),
            (
                "99\n00:09:01,000 --> 00:09:02,000\ntranslated a\n\n"
                "wrong-index\n00:09:03,000 --> 00:09:04,000\ntranslated b\n"
            ),
        )

        self.assertEqual(
            fixed,
            (
                "10\n00:00:01,000 --> 00:00:02,000\ntranslated a\n\n"
                "11\n00:00:03,000 --> 00:00:04,000\ntranslated b\n"
            ),
        )

    async def test_canonicalize_by_position_returns_none_on_count_mismatch(self):
        fixed = chunk_fix.canonicalize_by_position(
            "1\n00:00:01,000 --> 00:00:02,000\nsource\n",
            (
                "1\n00:00:01,000 --> 00:00:02,000\ntranslated\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\nextra\n"
            ),
        )

        self.assertIsNone(fixed)

    async def test_canonicalize_by_timecode_subset_fills_missing_source_blocks(self):
        fixed = chunk_fix.canonicalize_by_timecode_subset(
            (
                "10\n00:00:01,000 --> 00:00:02,000\nsource a\n\n"
                "11\n00:00:03,000 --> 00:00:04,000\nsource b\n\n"
                "12\n00:00:05,000 --> 00:00:06,000\nsource c\n"
            ),
            (
                "99\n00:00:01,000 --> 00:00:02,000\ntranslated a\n\n"
                "101\n00:00:05,000 --> 00:00:06,000\ntranslated c\n"
            ),
        )

        self.assertEqual(
            fixed,
            (
                "10\n00:00:01,000 --> 00:00:02,000\ntranslated a\n\n"
                "11\n00:00:03,000 --> 00:00:04,000\n\n\n"
                "12\n00:00:05,000 --> 00:00:06,000\ntranslated c\n"
            ),
        )

    async def test_canonicalize_by_timecode_subset_rejects_unexpected_timecode(self):
        fixed = chunk_fix.canonicalize_by_timecode_subset(
            "1\n00:00:01,000 --> 00:00:02,000\nsource\n",
            "1\n00:00:09,000 --> 00:00:10,000\ntranslated\n",
        )

        self.assertIsNone(fixed)

    async def test_canonicalize_by_aligned_sequence_fills_gap_between_anchors(self):
        with patch.object(
            chunk_fix.settings, "gemini_chunk_missing_block_tolerance", 2
        ):
            fixed = chunk_fix.canonicalize_by_aligned_sequence(
                (
                    "119\n00:00:01,000 --> 00:00:02,000\nsource 119\n\n"
                    "120\n00:00:03,000 --> 00:00:04,000\nsource 120\n\n"
                    "121\n00:00:05,000 --> 00:00:06,000\nsource 121\n\n"
                    "122\n00:00:07,000 --> 00:00:08,000\nsource 122\n"
                ),
                (
                    "1\n00:00:01,000 --> 00:00:02,000\ntranslated 119\n\n"
                    "2\n00:09:09,448 --> 00:11:56,310\ntranslated 120\n\n"
                    "3\n00:00:07,000 --> 00:00:08,000\ntranslated 122\n"
                ),
            )

        self.assertEqual(
            fixed,
            (
                "119\n00:00:01,000 --> 00:00:02,000\ntranslated 119\n\n"
                "120\n00:00:03,000 --> 00:00:04,000\ntranslated 120\n\n"
                "121\n00:00:05,000 --> 00:00:06,000\n\n\n"
                "122\n00:00:07,000 --> 00:00:08,000\ntranslated 122\n"
            ),
        )

    async def test_canonicalize_by_aligned_sequence_rejects_large_gap(self):
        with patch.object(
            chunk_fix.settings, "gemini_chunk_missing_block_tolerance", 2
        ):
            fixed = chunk_fix.canonicalize_by_aligned_sequence(
                (
                    "119\n00:00:01,000 --> 00:00:02,000\nsource 119\n\n"
                    "120\n00:00:03,000 --> 00:00:04,000\nsource 120\n\n"
                    "121\n00:00:05,000 --> 00:00:06,000\nsource 121\n\n"
                    "122\n00:00:07,000 --> 00:00:08,000\nsource 122\n\n"
                    "123\n00:00:09,000 --> 00:00:10,000\nsource 123\n\n"
                    "124\n00:00:11,000 --> 00:00:12,000\nsource 124\n"
                ),
                (
                    "1\n00:00:01,000 --> 00:00:02,000\ntranslated 119\n\n"
                    "2\n00:09:09,448 --> 00:11:56,310\ntranslated unknown\n\n"
                    "3\n00:00:11,000 --> 00:00:12,000\ntranslated 124\n"
                ),
            )

        self.assertIsNone(fixed)

    async def test_validate_output_fills_missing_blocks_with_empty_text(self):
        expected = [
            SrtBlock(
                index=10,
                timecode="00:00:01,000 --> 00:00:02,000",
                text="source a",
            ),
            SrtBlock(
                index=11,
                timecode="00:00:03,000 --> 00:00:04,000",
                text="source b",
            ),
        ]
        output = "99\n00:00:01,000 --> 00:00:02,000\ntranslated a\n"

        with patch.object(
            chunk_fix.settings, "gemini_chunk_missing_block_tolerance", 1
        ):
            blocks = _validate_output(expected, output)

        self.assertEqual(
            blocks,
            [
                SrtBlock(
                    index=10,
                    timecode="00:00:01,000 --> 00:00:02,000",
                    text="translated a",
                ),
                SrtBlock(
                    index=11,
                    timecode="00:00:03,000 --> 00:00:04,000",
                    text="",
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
