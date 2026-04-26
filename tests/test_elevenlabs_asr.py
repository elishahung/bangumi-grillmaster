import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.elevenlabs.asr import ElevenLabsASR


class ElevenLabsASRTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "tmp_elevenlabs_asr"
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def _run_transcription(self, response):
        root = self._make_temp_dir()
        audio_path = root / "audio.opus"
        json_path = root / "asr.json"
        audio_path.write_bytes(b"audio")

        with (
            patch("services.elevenlabs.asr.settings.elevenlabs_api_key", "key"),
            patch("services.elevenlabs.asr.ElevenLabs") as client_cls,
        ):
            client = client_cls.return_value
            client.speech_to_text.convert.return_value = response
            service = ElevenLabsASR()
            service.transcribe_to_file(audio_path, json_path)

        return json_path, client.speech_to_text.convert

    def test_writes_raw_response_json(self):
        response = {
            "text": "こんにちは",
            "words": [],
        }

        json_path, convert = self._run_transcription(response)

        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), response)
        _, kwargs = convert.call_args
        self.assertEqual(kwargs["model_id"], "scribe_v2")
        self.assertEqual(kwargs["language_code"], "jpn")
        self.assertEqual(kwargs["timestamps_granularity"], "word")
        self.assertTrue(kwargs["diarize"])
        self.assertNotIn("additional_formats", kwargs)

    def test_accepts_sdk_model_dump_response(self):
        response = MagicMock()
        response.model_dump.return_value = {
            "text": "こんにちは",
            "words": [],
        }

        json_path, _ = self._run_transcription(response)

        self.assertEqual(
            json.loads(json_path.read_text(encoding="utf-8")),
            response.model_dump.return_value,
        )


if __name__ == "__main__":
    unittest.main()
