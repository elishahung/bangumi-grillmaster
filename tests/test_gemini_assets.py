import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from services.gemini.assets import (
    LocalMediaRef,
    media_ref_to_part,
    prepare_chunk_media_assets,
    prepare_pre_pass_media_assets,
)
from services.gemini.chunker import SrtBlock


class GeminiAssetsTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"tmp_assets_{uuid.uuid4().hex[:8]}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_prepare_pre_pass_media_assets_uses_interval_spacing(self):
        root = self._make_temp_dir()
        video_path = root / "video.mp4"
        audio_path = root / "audio.opus"

        with (
            patch(
                "services.gemini.assets.MediaProcessor.get_media_duration",
                return_value=305.0,
            ),
            patch(
                "services.gemini.assets.MediaProcessor.extract_video_frame"
            ) as extract_frame,
        ):
            assets = prepare_pre_pass_media_assets(
                video_path=video_path,
                audio_path=audio_path,
                cache_root=root / "pre_pass",
                interval_seconds=120,
                max_side=768,
            )

        self.assertEqual(
            [frame.timestamp_seconds for frame in assets.frames],
            [0.0, 120.0, 240.0, 304.9],
        )
        self.assertEqual(extract_frame.call_count, 4)
        self.assertEqual(assets.audio.path, audio_path)
        self.assertEqual(assets.audio.mime_type, "audio/ogg")
        self.assertTrue(assets.manifest_path.exists())
        manifest = json.loads(
            assets.manifest_path.read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["interval_seconds"], 120)
        self.assertEqual(manifest["frames"][0]["mime_type"], "image/jpeg")
        self.assertEqual(manifest["audio"]["path"], str(audio_path))

    def test_prepare_chunk_media_assets_includes_chunk_start_and_interval(self):
        chunk = [
            SrtBlock(
                index=1,
                timecode="00:01:01,000 --> 00:01:02,000",
                text="a",
            ),
            SrtBlock(
                index=2,
                timecode="00:02:59,000 --> 00:03:00,000",
                text="b",
            ),
        ]

        root = self._make_temp_dir()
        video_path = root / "video.mp4"
        audio_path = root / "audio.opus"

        with (
            patch(
                "services.gemini.assets.MediaProcessor.extract_audio_segment"
            ),
            patch(
                "services.gemini.assets.MediaProcessor.extract_video_frame"
            ),
        ):
            assets = prepare_chunk_media_assets(
                video_path=video_path,
                audio_path=audio_path,
                cache_root=root / "chunks",
                video_key="video-key",
                chunk=chunk,
                chunk_index=0,
                total_chunks=2,
                interval_seconds=60,
                max_side=768,
            )

        self.assertEqual(
            [frame.timestamp_seconds for frame in assets.frames],
            [61.0, 120.0, 180.0],
        )
        manifest = json.loads(
            assets.manifest_path.read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["interval_seconds"], 60)
        self.assertEqual(manifest["max_side"], 768)
        self.assertEqual(manifest["audio"]["path"], str(assets.audio.path))
        self.assertEqual(manifest["frames"][0]["mime_type"], "image/jpeg")

    def test_media_ref_to_part_reads_bytes_and_mime_type(self):
        root = self._make_temp_dir()
        media_path = root / "frame.jpg"
        media_path.write_bytes(b"image-bytes")

        part = media_ref_to_part(
            LocalMediaRef(path=media_path, mime_type="image/jpeg")
        )

        self.assertEqual(part.inline_data.data, b"image-bytes")
        self.assertEqual(part.inline_data.mime_type, "image/jpeg")

    def test_media_ref_to_part_raises_for_missing_file(self):
        root = self._make_temp_dir()

        with self.assertRaises(FileNotFoundError):
            media_ref_to_part(
                LocalMediaRef(
                    path=root / "missing.opus",
                    mime_type="audio/ogg",
                )
            )


if __name__ == "__main__":
    unittest.main()
