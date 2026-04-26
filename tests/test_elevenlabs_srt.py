import json
import shutil
import unittest
from pathlib import Path

from services.elevenlabs.srt import SrtFormatOptions, convert_file, convert_payload_to_srt


def word(text, start, end, speaker="speaker_0"):
    return {
        "text": text,
        "start": start,
        "end": end,
        "type": "word",
        "speaker_id": speaker,
        "logprob": 0.0,
    }


class ElevenLabsSrtTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "tmp_elevenlabs_srt"
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_splits_japanese_hard_punctuation(self):
        payload = {
            "words": [
                word("これは", 0.0, 0.4),
                word("テスト", 0.4, 0.8),
                word("です。", 0.8, 1.0),
                word("次", 1.1, 1.3),
                word("です？", 1.3, 1.6),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("これはテストです。", srt)
        self.assertIn("次です？", srt)
        self.assertIn("00:00:00,000 --> 00:00:01,000", srt)
        self.assertIn("00:00:01,100 --> 00:00:01,600", srt)

    def test_merges_close_speaker_turns_as_dialogue_without_speaker_ids(self):
        payload = {
            "words": [
                word("馬の", 0.0, 0.3, "speaker_0"),
                word("頭企画", 0.3, 0.8, "speaker_0"),
                word("とかより", 0.8, 1.2, "speaker_0"),
                word("いいでしょ。", 1.2, 1.7, "speaker_0"),
                word("あれは", 1.95, 2.2, "speaker_1"),
                word("嫌だ", 2.2, 2.45, "speaker_1"),
                word("もう。", 2.45, 2.7, "speaker_1"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("-馬の頭企画とかよりいいでしょ。", srt)
        self.assertIn("-あれは嫌だもう。", srt)
        self.assertNotIn("speaker_0", srt)
        self.assertNotIn("speaker_1", srt)

    def test_does_not_start_segment_with_japanese_particle(self):
        payload = {
            "words": [
                word("酒", 79.06, 79.26),
                word("に", 79.26, 79.42),
                word("花", 79.42, 79.6),
                word("び", 79.6, 79.68),
                word("ら", 79.74, 79.84),
                word("を", 79.84, 79.96),
                word("落", 79.96, 80.1),
                word("と", 80.1, 80.22),
                word("し", 80.22, 80.76),
                word("、", 80.76, 80.76),
                word("風", 80.9, 81.12),
                word("流", 81.12, 81.52),
                word("な", 81.52, 81.86),
                word("花", 81.86, 82.24),
                word("見", 82.24, 82.36),
                word("を", 82.36, 84.14),
                word("。", 84.14, 84.14),
            ]
        }

        srt = convert_payload_to_srt(
            payload,
            SrtFormatOptions(max_segment_chars=20, max_segment_duration_s=4.0),
        )

        self.assertIn("花見を。", srt)
        self.assertNotIn("\nを。\n", srt)

    def test_merges_overlapping_blocks_from_zero_length_speaker_turns(self):
        payload = {
            "words": [
                word("あ", 44.14, 44.2, "speaker_0"),
                word("り", 44.2, 44.28, "speaker_0"),
                word("が", 44.28, 44.42, "speaker_0"),
                word("と", 44.42, 44.52, "speaker_0"),
                word("う", 44.52, 44.53, "speaker_0"),
                word("。", 44.53, 44.53, "speaker_0"),
                word("来", 44.53, 44.53, "speaker_1"),
                word("た", 44.53, 44.53, "speaker_1"),
                word("よ", 44.53, 44.53, "speaker_1"),
                word("。", 44.53, 44.53, "speaker_1"),
                word("あ", 44.53, 44.53, "speaker_1"),
                word("り", 44.53, 44.53, "speaker_1"),
                word("が", 44.53, 44.53, "speaker_1"),
                word("と", 44.53, 44.53, "speaker_1"),
                word("う", 44.53, 44.53, "speaker_1"),
                word("。", 44.53, 44.53, "speaker_1"),
                word("援", 44.58, 44.7, "speaker_1"),
                word("軍", 44.7, 44.98, "speaker_1"),
                word("だ", 44.98, 45.3, "speaker_1"),
                word("。", 45.3, 45.3, "speaker_1"),
                word("い", 45.36, 45.46, "speaker_0"),
                word("い", 45.46, 45.56, "speaker_0"),
                word("で", 45.56, 45.62, "speaker_0"),
                word("し", 45.62, 45.68, "speaker_0"),
                word("ょ", 45.68, 45.96, "speaker_0"),
                word("、", 45.96, 45.96, "speaker_0"),
                word("今", 46.0, 46.04, "speaker_0"),
                word("日", 46.04, 46.18, "speaker_0"),
                word("は", 46.18, 46.34, "speaker_0"),
                word("。", 46.34, 46.34, "speaker_0"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("1\n00:00:44,140 --> 00:00:44,530", srt)
        self.assertIn("-ありがとう。", srt)
        self.assertIn("-来たよ。", srt)
        self.assertNotIn("00:00:44,530 --> 00:00:44,530", srt)

    def test_limits_dialogue_block_height_after_overlap_merge(self):
        payload = {
            "words": [
                word("一。", 0.0, 0.1, "speaker_0"),
                word("二。", 0.1, 0.1, "speaker_1"),
                word("三。", 0.1, 0.1, "speaker_1"),
                word("四。", 0.2, 0.2, "speaker_1"),
                word("五。", 0.3, 0.3, "speaker_0"),
                word("六。", 0.5, 0.6, "speaker_1"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("1\n00:00:00,000 --> 00:00:00,450\n-一。\n-二。", srt)
        self.assertIn("2\n00:00:00,450 --> 00:00:00,800\n三。", srt)
        self.assertIn("3\n00:00:00,800 --> 00:00:01,150\n-四。\n-五。", srt)
        self.assertIn("4\n00:00:01,150 --> 00:00:01,500\n六。", srt)

    def test_does_not_merge_reply_when_dialogue_would_exceed_two_lines(self):
        payload = {
            "words": [
                word("ということで、", 22.72, 23.5, "speaker_0"),
                word("今回やるんやけど、", 23.6, 24.6, "speaker_0"),
                word("前は", 24.72, 25.32, "speaker_0"),
                word("1時間", 25.56, 26.02, "speaker_0"),
                word("2時間ぐらいかかって。", 26.14, 26.94, "speaker_0"),
                word("かかりました。", 27.02, 27.5, "speaker_1"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn(
            "1\n00:00:22,720 --> 00:00:26,940\n"
            "ということで、今回やるんやけど、\n"
            "前は1時間2時間ぐらいかかって。",
            srt,
        )
        self.assertIn("2\n00:00:27,020 --> 00:00:27,500\nかかりました。", srt)
        self.assertNotIn("-かかりました。", srt)

    def test_limits_close_three_speaker_turns_to_two_lines(self):
        payload = {
            "words": [
                word("一番流行ってるってスパイス。", 247.2, 248.48, "speaker_3"),
                word("ニューヨークで流行ってるスパイス？", 248.62, 250.46, "speaker_0"),
                word("そう。", 250.47, 250.8, "speaker_3"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("-一番流行ってるってスパイス。", srt)
        self.assertIn("-ニューヨークで流行ってるスパイス？", srt)
        self.assertIn("2\n00:04:10,470 --> 00:04:10,820\nそう。", srt)
        self.assertNotIn("-そう。", srt)

    def test_does_not_merge_speaker_turns_when_gap_is_too_large(self):
        payload = {
            "words": [
                word("先です。", 0.0, 0.5, "speaker_0"),
                word("後です。", 2.0, 2.5, "speaker_1"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("1\n00:00:00,000 --> 00:00:00,500\n先です。", srt)
        self.assertIn("2\n00:00:02,000 --> 00:00:02,500\n後です。", srt)
        self.assertNotIn("-先です。", srt)

    def test_respects_common_segment_options(self):
        payload = {
            "words": [
                word("一", 0.0, 0.3),
                word("二", 0.3, 0.6),
                word("三", 0.6, 0.9),
                word("四", 0.9, 1.2),
            ]
        }

        srt = convert_payload_to_srt(
            payload,
            SrtFormatOptions(max_segment_chars=2, max_characters_per_line=2),
        )

        self.assertIn("1\n00:00:00,000 --> 00:00:00,600\n一二", srt)
        self.assertIn("2\n00:00:00,600 --> 00:00:01,200\n三四", srt)

    def test_convert_file_writes_srt(self):
        root = self._make_temp_dir()
        input_path = root / "asr.json"
        output_path = root / "video.ja.srt"
        input_path.write_text(
            json.dumps({"words": [word("はい。", 0.0, 0.4)]}, ensure_ascii=False),
            encoding="utf-8",
        )

        convert_file(input_path, output_path)

        self.assertEqual(
            output_path.read_text(encoding="utf-8"),
            "1\n00:00:00,000 --> 00:00:00,400\nはい。\n",
        )

    def test_raises_when_json_has_no_timed_words(self):
        with self.assertRaisesRegex(ValueError, "timed words"):
            convert_payload_to_srt({"words": [{"text": "はい", "type": "word"}]})


if __name__ == "__main__":
    unittest.main()
