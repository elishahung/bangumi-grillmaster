import tempfile
import unittest
from pathlib import Path

from services.fun_asr.models import FunASRResult
from services.fun_asr.srt import convert_file
from services.media import WAV_SAMPLE_RATE
from services.qwen3_asr.qwen3_asr import qwen_results_to_fun_asr_json
from services.qwen3_asr.vad import (
    AudioChunk,
    plan_vad_chunks,
)


class FakeTimestamp:
    def __init__(self, text: str, start_time: float, end_time: float):
        self.text = text
        self.start_time = start_time
        self.end_time = end_time


class FakeResult:
    def __init__(self, text: str, time_stamps=None):
        self.text = text
        self.time_stamps = time_stamps


class Qwen3ASRTests(unittest.TestCase):
    def test_short_audio_stays_one_chunk(self):
        chunks = plan_vad_chunks(
            total_samples=30 * WAV_SAMPLE_RATE,
            speech_timestamps=[],
        )

        self.assertEqual(chunks, [AudioChunk(0, 30 * WAV_SAMPLE_RATE)])

    def test_no_speech_fallback_respects_max_segment_duration(self):
        chunks = plan_vad_chunks(
            total_samples=400 * WAV_SAMPLE_RATE,
            speech_timestamps=[],
            max_segment_threshold_s=180,
        )

        self.assertEqual(len(chunks), 3)
        self.assertTrue(
            all(
                chunk.end_sample - chunk.start_sample <= 180 * WAV_SAMPLE_RATE
                for chunk in chunks
            )
        )
        self.assertEqual(chunks[0].start_sample, 0)
        self.assertEqual(chunks[-1].end_sample, 400 * WAV_SAMPLE_RATE)

    def test_vad_chunks_split_near_speech_boundaries_and_respect_max(self):
        chunks = plan_vad_chunks(
            total_samples=400 * WAV_SAMPLE_RATE,
            speech_timestamps=[
                {"start": 118 * WAV_SAMPLE_RATE, "end": 130 * WAV_SAMPLE_RATE},
                {"start": 239 * WAV_SAMPLE_RATE, "end": 250 * WAV_SAMPLE_RATE},
            ],
            segment_threshold_s=120,
            max_segment_threshold_s=180,
        )

        self.assertEqual(chunks[0].start_sample, 0)
        self.assertEqual(chunks[-1].end_sample, 400 * WAV_SAMPLE_RATE)
        self.assertTrue(
            all(
                chunk.end_sample - chunk.start_sample <= 180 * WAV_SAMPLE_RATE
                for chunk in chunks
            )
        )
        self.assertIn(
            118 * WAV_SAMPLE_RATE,
            [chunk.end_sample for chunk in chunks],
        )

    def test_qwen_result_converts_to_fun_asr_json(self):
        result = qwen_results_to_fun_asr_json(
            file_path=Path("audio.opus"),
            total_samples=10 * WAV_SAMPLE_RATE,
            chunks=[AudioChunk(0, 10 * WAV_SAMPLE_RATE)],
            results=[
                FakeResult(
                    "こんにちは 世界",
                    [
                        FakeTimestamp("こんにちは", 0.25, 1.0),
                        FakeTimestamp("世界", 1.1, 2.0),
                    ],
                )
            ],
        )

        parsed = FunASRResult.model_validate(result)
        sentences = parsed.transcripts[0].sentences
        self.assertEqual(parsed.transcripts[0].text, "こんにちは 世界")
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].begin_time, 250)
        self.assertEqual(sentences[0].end_time, 2000)
        self.assertEqual(sentences[0].text, "こんにちは世界")
        self.assertEqual(len(sentences[0].words), 2)

    def test_qwen_token_timestamps_are_grouped_into_subtitle_sentence(self):
        result = qwen_results_to_fun_asr_json(
            file_path=Path("audio.opus"),
            total_samples=10 * WAV_SAMPLE_RATE,
            chunks=[AudioChunk(0, 10 * WAV_SAMPLE_RATE)],
            results=[
                FakeResult(
                    "酒に桜を浮かべ",
                    [
                        FakeTimestamp("酒", 0.0, 0.1),
                        FakeTimestamp("に", 0.1, 0.2),
                        FakeTimestamp("桜", 0.2, 0.3),
                        FakeTimestamp("を", 0.3, 0.4),
                        FakeTimestamp("浮かべ", 0.4, 0.8),
                    ],
                )
            ],
        )

        sentences = FunASRResult.model_validate(result).transcripts[0].sentences
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].begin_time, 0)
        self.assertEqual(sentences[0].end_time, 800)
        self.assertEqual(sentences[0].text, "酒に桜を浮かべ")

    def test_qwen_result_without_timestamps_uses_chunk_bounds(self):
        result = qwen_results_to_fun_asr_json(
            file_path=Path("audio.opus"),
            total_samples=10 * WAV_SAMPLE_RATE,
            chunks=[AudioChunk(2 * WAV_SAMPLE_RATE, 5 * WAV_SAMPLE_RATE)],
            results=[FakeResult("fallback text", [])],
        )

        sentence = (
            FunASRResult.model_validate(result).transcripts[0].sentences[0]
        )
        self.assertEqual(sentence.begin_time, 2000)
        self.assertEqual(sentence.end_time, 5000)
        self.assertEqual(sentence.text, "fallback text")

    def test_fun_asr_srt_converter_accepts_qwen_json_shape(self):
        result = qwen_results_to_fun_asr_json(
            file_path=Path("audio.opus"),
            total_samples=3 * WAV_SAMPLE_RATE,
            chunks=[AudioChunk(0, 3 * WAV_SAMPLE_RATE)],
            results=[FakeResult("字幕テスト", [])],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "asr.json"
            output_path = Path(tmp_dir) / "video.ja.srt"
            input_path.write_text(
                FunASRResult.model_validate(result).model_dump_json(),
                encoding="utf-8",
            )

            convert_file(input_path, output_path)

            srt = output_path.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:03,000", srt)
            self.assertIn("字幕テスト", srt)


if __name__ == "__main__":
    unittest.main()
