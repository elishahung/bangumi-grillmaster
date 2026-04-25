import asyncio
import unittest
from unittest.mock import patch

from services.gemini.errors import ChunkFixError
from services.llm import chunk_fix


class ChunkFixTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_fix_chunk_structure_times_out_hung_litellm_call(self):
        async def hung_acompletion(**_kwargs):
            await asyncio.Event().wait()

        with (
            patch.object(chunk_fix, "acompletion", hung_acompletion),
            patch.object(chunk_fix, "LITELLM_TIMEOUT_SECONDS", 0.01),
            patch.object(chunk_fix.settings, "llm_chunk_fix_max_retries", 1),
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


if __name__ == "__main__":
    unittest.main()
