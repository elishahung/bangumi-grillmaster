import asyncio
import shutil
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from services.gemini.storage import GeminiFileRef, GeminiStorage


class _FakeFilesClient:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def get(self, name: str):
        time.sleep(0.02)
        return None

    def upload(self, file: Path, config):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.05)
            return {"name": config.name, "file": str(file)}
        finally:
            with self.lock:
                self.active -= 1


class _FakeClient:
    def __init__(self):
        self.files = _FakeFilesClient()


class GeminiStorageTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"tmp_storage_{uuid.uuid4().hex[:8]}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_ensure_files_runs_concurrently_and_preserves_order(self):
        root = self._make_temp_dir()
        refs = []
        for index in range(6):
            file_path = root / f"{index}.jpg"
            file_path.write_bytes(b"image")
            refs.append(
                GeminiFileRef(
                    key=f"frame-{index}",
                    file_path=file_path,
                    mime_type="image/jpeg",
                )
            )

        client = _FakeClient()
        storage = GeminiStorage(client)

        with patch("services.gemini.storage.settings.gemini_file_concurrency", 3):
            files = asyncio.run(storage.ensure_files(refs))

        self.assertEqual(
            [item["file"] for item in files],
            [str(ref.file_path) for ref in refs],
        )
        self.assertLessEqual(client.files.max_active, 3)
        self.assertGreater(client.files.max_active, 1)

    def test_ensure_files_concurrency_is_global_per_storage_client(self):
        root = self._make_temp_dir()
        refs = []
        for index in range(8):
            file_path = root / f"{index}.jpg"
            file_path.write_bytes(b"image")
            refs.append(
                GeminiFileRef(
                    key=f"frame-{index}",
                    file_path=file_path,
                    mime_type="image/jpeg",
                )
            )

        client = _FakeClient()
        storage = GeminiStorage(client)

        async def run_two_batches():
            first, second = await asyncio.gather(
                storage.ensure_files(refs[:4]),
                storage.ensure_files(refs[4:]),
            )
            return first, second

        with patch("services.gemini.storage.settings.gemini_file_concurrency", 3):
            first, second = asyncio.run(run_two_batches())

        self.assertEqual(
            [item["file"] for item in first],
            [str(ref.file_path) for ref in refs[:4]],
        )
        self.assertEqual(
            [item["file"] for item in second],
            [str(ref.file_path) for ref in refs[4:]],
        )
        self.assertLessEqual(client.files.max_active, 3)
        self.assertGreater(client.files.max_active, 1)


if __name__ == "__main__":
    unittest.main()
