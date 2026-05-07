import shutil
import unittest
from pathlib import Path

from services.ass.converter import (
    ASS_HEADER,
    _block_to_dialogue,
    _clean_text,
    _srt_timecode_to_ass,
    convert_file,
)
from services.gemini.chunker import SrtBlock


class AssConverterTextCleaningTests(unittest.TestCase):
    def test_replaces_comma_with_space(self):
        self.assertEqual(_clean_text("你好，今天天氣不錯"), "你好 今天天氣不錯")

    def test_removes_full_stop(self):
        self.assertEqual(_clean_text("今天天氣不錯。"), "今天天氣不錯")

    def test_replaces_enumeration_comma_with_space(self):
        self.assertEqual(_clean_text("蘋果、橘子、香蕉"), "蘋果 橘子 香蕉")

    def test_replaces_semicolon_with_space(self):
        self.assertEqual(_clean_text("一；二；三"), "一 二 三")

    def test_combined_punctuation(self):
        # `。` is removed without inserting a separator (Netflix rule); typically
        # appears at end-of-line so adjacent clauses joining is rare in practice.
        self.assertEqual(
            _clean_text("你好，今天天氣不錯。蘋果、橘子、香蕉。"),
            "你好 今天天氣不錯蘋果 橘子 香蕉",
        )

    def test_preserves_question_and_exclamation(self):
        self.assertEqual(_clean_text("真的嗎？太好了！"), "真的嗎？太好了！")

    def test_preserves_quotes_parens_ellipsis_colon(self):
        self.assertEqual(
            _clean_text("「結論：很好吃……」"),
            "「結論：很好吃……」",
        )
        self.assertEqual(_clean_text("（旁白）"), "（旁白）")

    def test_strips_leading_and_trailing_whitespace(self):
        # Trailing space comes from a comma at end of line.
        self.assertEqual(_clean_text("你好，"), "你好")
        # Leading space comes from a comma at start of line.
        self.assertEqual(_clean_text("，你好"), "你好")

    def test_collapses_consecutive_spaces_from_adjacent_punctuation(self):
        self.assertEqual(_clean_text("好，、的"), "好 的")

    def test_processes_multiline_text_per_line(self):
        self.assertEqual(
            _clean_text("第一行，\n第二行。"),
            "第一行\n第二行",
        )


class AssTimecodeTests(unittest.TestCase):
    def test_converts_srt_timecode_to_ass_pair(self):
        start, end = _srt_timecode_to_ass(
            "00:00:01,500 --> 00:00:02,750"
        )
        self.assertEqual(start, "0:00:01.50")
        self.assertEqual(end, "0:00:02.75")

    def test_strips_hour_leading_zero(self):
        start, end = _srt_timecode_to_ass(
            "01:23:45,678 --> 12:00:00,000"
        )
        self.assertEqual(start, "1:23:45.67")
        self.assertEqual(end, "12:00:00.00")

    def test_truncates_milliseconds_to_centiseconds(self):
        # 999 ms → 99 cs (Aegisub-style truncation, not rounding).
        start, _ = _srt_timecode_to_ass(
            "00:00:00,999 --> 00:00:01,000"
        )
        self.assertEqual(start, "0:00:00.99")

    def test_rejects_invalid_timecode(self):
        with self.assertRaises(ValueError):
            _srt_timecode_to_ass("garbage")


class AssDialogueTests(unittest.TestCase):
    def test_block_to_dialogue_emits_default_style_and_zero_margins(self):
        block = SrtBlock(
            index=1,
            timecode="00:00:01,000 --> 00:00:02,000",
            text="你好，世界。",
        )
        line = _block_to_dialogue(block)
        self.assertEqual(
            line,
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好 世界",
        )

    def test_block_to_dialogue_converts_newline_to_ass_soft_break(self):
        block = SrtBlock(
            index=1,
            timecode="00:00:01,000 --> 00:00:02,000",
            text="第一行，\n第二行。",
        )
        line = _block_to_dialogue(block)
        self.assertIn("第一行\\N第二行", line)

    def test_block_with_empty_text_still_emits_dialogue(self):
        block = SrtBlock(
            index=1,
            timecode="00:00:01,000 --> 00:00:02,000",
            text="",
        )
        line = _block_to_dialogue(block)
        self.assertEqual(
            line,
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,",
        )


class AssConvertFileTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "tmp_ass_converter"
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_convert_file_writes_styled_ass_with_cleaned_text(self):
        tmp = self._make_temp_dir()
        srt_path = tmp / "input.srt"
        ass_path = tmp / "output.ass"

        srt_path.write_text(
            "1\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "你好，世界。\n"
            "\n"
            "2\n"
            "00:00:03,500 --> 00:00:05,250\n"
            "真的嗎？太好了！\n",
            encoding="utf-8",
        )

        convert_file(srt_path, ass_path)

        out = ass_path.read_text(encoding="utf-8")
        self.assertTrue(out.startswith(ASS_HEADER))
        self.assertIn("[Script Info]", out)
        self.assertIn("PlayResX: 1920", out)
        self.assertIn("Style: Default,源泉圓體月 B,64,", out)
        self.assertIn(
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好 世界",
            out,
        )
        self.assertIn(
            "Dialogue: 0,0:00:03.50,0:00:05.25,Default,,0,0,0,,真的嗎？太好了！",
            out,
        )

    def test_convert_file_creates_output_parent_directory(self):
        tmp = self._make_temp_dir()
        srt_path = tmp / "input.srt"
        ass_path = tmp / "nested" / "out.ass"

        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n你好。\n",
            encoding="utf-8",
        )

        convert_file(srt_path, ass_path)
        self.assertTrue(ass_path.exists())


if __name__ == "__main__":
    unittest.main()
