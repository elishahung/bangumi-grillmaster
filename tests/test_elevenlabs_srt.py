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

    def test_inlines_short_repeated_same_speaker_utterances(self):
        payload = {
            "words": [
                word("何", 1320.72, 1320.88, "speaker_8"),
                word("？", 1320.88, 1320.9, "speaker_8"),
                word("何", 1320.9, 1320.91, "speaker_8"),
                word("？", 1320.91, 1321.02, "speaker_8"),
                word("何", 1321.02, 1321.52, "speaker_8"),
                word("？", 1321.52, 1323.22, "speaker_8"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("1\n00:22:00,720 --> 00:22:03,220\n何？ 何？ 何？", srt)
        self.assertNotIn("何？\n何？\n何？", srt)

    def test_keeps_long_same_speaker_utterances_stacked_after_overlap_merge(self):
        payload = {
            "words": [
                word("これは長めの質問です？", 0.0, 0.2, "speaker_0"),
                word("これも長めの返答です。", 0.2, 0.4, "speaker_0"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("これは長めの質問です？\nこれも長めの返答です。", srt)

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

    def test_keeps_short_sentence_tail_with_previous_long_utterance(self):
        payload = {
            "words": [
                word("続", 409.55, 409.65, "speaker_1"),
                word("い", 409.65, 409.75, "speaker_1"),
                word("て", 409.75, 409.83, "speaker_1"),
                word("決", 409.83, 410.07, "speaker_1"),
                word("勝", 410.17, 410.25, "speaker_1"),
                word("２", 410.29, 410.59, "speaker_1"),
                word("組", 410.59, 410.93, "speaker_1"),
                word("目", 410.93, 411.27, "speaker_1"),
                word("、", 411.27, 411.27, "speaker_1"),
                word("B", 411.31, 411.33, "speaker_1"),
                word("ブ", 411.59, 411.67, "speaker_1"),
                word("ロ", 411.67, 411.73, "speaker_1"),
                word("ッ", 411.73, 411.89, "speaker_1"),
                word("ク", 411.89, 412.03, "speaker_1"),
                word("を", 412.03, 412.15, "speaker_1"),
                word("勝", 412.15, 412.31, "speaker_1"),
                word("ち", 412.31, 412.45, "speaker_1"),
                word("上", 412.45, 412.49, "speaker_1"),
                word("が", 412.49, 412.63, "speaker_1"),
                word("っ", 412.63, 412.71, "speaker_1"),
                word("た", 412.71, 412.77, "speaker_1"),
                word("の", 412.77, 412.85, "speaker_1"),
                word("は", 412.85, 413.03, "speaker_1"),
                word("こ", 413.03, 413.25, "speaker_1"),
                word("の", 413.25, 413.39, "speaker_1"),
                word("コ", 413.39, 413.45, "speaker_1"),
                word("ン", 413.45, 413.55, "speaker_1"),
                word("ビ", 413.55, 413.69, "speaker_1"),
                word("で", 413.69, 413.81, "speaker_1"),
                word("す", 413.81, 413.83, "speaker_1"),
                word("。", 413.83, 413.83, "speaker_1"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("00:06:49,550 --> 00:06:53,830", srt)
        self.assertNotIn("\n2\n", srt)

    def test_keeps_question_tail_before_close_speaker_reply(self):
        payload = {
            "words": [
                word("さ", 1056.0, 1056.12, "speaker_9"),
                word("あ", 1056.12, 1056.34, "speaker_9"),
                word("皆", 1056.34, 1056.48, "speaker_9"),
                word("さ", 1056.48, 1056.56, "speaker_9"),
                word("ん", 1056.56, 1056.66, "speaker_9"),
                word("、", 1056.66, 1056.66, "speaker_9"),
                word("最", 1056.78, 1056.98, "speaker_9"),
                word("後", 1056.98, 1057.08, "speaker_9"),
                word("の", 1057.08, 1057.22, "speaker_9"),
                word("投", 1057.22, 1057.46, "speaker_9"),
                word("票", 1057.52, 1057.7, "speaker_9"),
                word("前", 1057.7, 1057.78, "speaker_9"),
                word("に", 1057.78, 1058.04, "speaker_9"),
                word("一", 1058.04, 1058.24, "speaker_9"),
                word("言", 1058.24, 1058.62, "speaker_9"),
                word("ず", 1058.62, 1058.68, "speaker_9"),
                word("つ", 1058.68, 1059.08, "speaker_9"),
                word("羊", 1059.08, 1059.32, "speaker_9"),
                word("寝", 1059.32, 1059.4, "speaker_9"),
                word("入", 1059.4, 1059.58, "speaker_9"),
                word("り", 1059.58, 1059.76, "speaker_9"),
                word("い", 1059.76, 1059.84, "speaker_9"),
                word("か", 1059.84, 1059.98, "speaker_9"),
                word("が", 1059.98, 1060.02, "speaker_9"),
                word("で", 1060.02, 1060.2, "speaker_9"),
                word("す", 1060.2, 1060.3, "speaker_9"),
                word("か", 1060.3, 1060.46, "speaker_9"),
                word("？", 1060.46, 1060.54, "speaker_9"),
                word("は", 1060.6, 1060.66, "speaker_10"),
                word("い", 1060.66, 1060.84, "speaker_10"),
                word("、", 1060.84, 1060.84, "speaker_10"),
                word("ちょっと", 1060.86, 1061.12, "speaker_10"),
                word("うちだけ", 1061.12, 1061.86, "speaker_10"),
                word("推薦人が", 1061.86, 1062.36, "speaker_10"),
                word("帰ってしまったんですけど。", 1062.36, 1063.5, "speaker_10"),
            ]
        }

        srt = convert_payload_to_srt(payload)

        self.assertIn("ですか？", srt)
        self.assertIn("2\n00:17:40,600", srt)
        self.assertNotIn("-すか？", srt)

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
