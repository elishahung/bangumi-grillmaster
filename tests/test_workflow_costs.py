import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import workflow as workflow_module
from services.elevenlabs.asr import ElevenLabsTranscriptionResult
from services.gemini.errors import GeminiTranslationError, TranslationCostSummary


class WorkflowGeminiCostTests(unittest.TestCase):
    def _build_project_mock(self):
        project = MagicMock()
        project.id = "demo"
        project.translation_hint = "hint"
        project.total_cost = 0.0
        project.is_metadata_fetched = True
        project.is_downloaded = True
        project.is_video_processed = True
        project.is_audio_processed = True
        project.is_asr_completed = True
        project.is_srt_completed = True
        project.is_translated = False
        base = Path("projects/demo")
        project.srt_path = base / "video.ja.srt"
        project.video_path = base / "video.mp4"
        project.audio_path = base / ".asr" / "audio.opus"
        project.translated_path = base / "video.cht.srt"
        project.pre_pass_path = base / ".pre_pass" / "pre_pass.json"
        project.pre_pass_cache_dir = base / ".pre_pass"
        project.chunks_cache_dir = base / ".chunks"
        return project

    def test_workflow_persists_gemini_cost_on_success(self):
        project = self._build_project_mock()
        summary = TranslationCostSummary(
            total_cost=3.5,
            pre_pass_cost=1.0,
            chunk_costs=[1.0, 1.5],
            num_chunks=2,
            retries=1,
            elapsed_seconds=5.0,
            completed_chunks=2,
            failed_chunks=[],
        )

        with (
            patch.object(
                workflow_module.Project, "from_source_str", return_value=project
            ),
            patch.object(workflow_module, "Gemini") as gemini_cls,
            patch.object(workflow_module.settings, "archived_path", None),
        ):
            gemini_cls.return_value.translate.return_value = summary
            workflow_module.process_project("demo")

        project.add_cost.assert_called_once_with("gemini", 3.5)
        project.mark_progress.assert_called_once_with(
            workflow_module.ProgressStage.TRANSLATED
        )

    def test_workflow_persists_partial_gemini_cost_on_failure(self):
        project = self._build_project_mock()
        summary = TranslationCostSummary(
            total_cost=2.25,
            pre_pass_cost=0.75,
            chunk_costs=[1.5, 0.0],
            num_chunks=2,
            retries=2,
            elapsed_seconds=4.0,
            completed_chunks=1,
            failed_chunks=["[chunk 2/2] index 11-20: failed"],
        )

        with (
            patch.object(
                workflow_module.Project, "from_source_str", return_value=project
            ),
            patch.object(workflow_module, "Gemini") as gemini_cls,
            patch.object(workflow_module.settings, "archived_path", None),
        ):
            gemini_cls.return_value.translate.side_effect = (
                GeminiTranslationError("translation failed", summary)
            )
            with self.assertRaises(GeminiTranslationError):
                workflow_module.process_project("demo")

        project.add_cost.assert_called_once_with("gemini", 2.25)
        project.mark_progress.assert_not_called()


class WorkflowElevenLabsCostTests(unittest.TestCase):
    def _build_project_mock(self):
        project = MagicMock()
        project.id = "demo"
        project.total_cost = 0.0
        project.is_metadata_fetched = True
        project.is_downloaded = True
        project.is_video_processed = True
        project.is_audio_processed = True
        project.is_asr_completed = False
        project.is_srt_completed = False
        project.is_translated = False
        base = Path("projects/demo")
        project.audio_path = base / ".asr" / "audio.opus"
        project.asr_path = base / ".asr" / "asr.json"
        project.srt_path = base / "video.ja.srt"
        return project

    def test_workflow_persists_elevenlabs_cost_on_asr_success(self):
        project = self._build_project_mock()
        result = ElevenLabsTranscriptionResult(
            audio_duration_secs=1800,
            total_cost=0.11,
        )

        with (
            patch.object(
                workflow_module.Project, "from_source_str", return_value=project
            ),
            patch.object(workflow_module, "ElevenLabsASR") as elevenlabs_cls,
            patch.object(workflow_module, "convert_file") as convert_file,
            patch.object(workflow_module, "Gemini") as gemini_cls,
        ):
            elevenlabs_cls.return_value.transcribe_to_file.return_value = result
            workflow_module.process_project(
                "demo",
                break_after=workflow_module.ProgressStage.ASR_COMPLETED,
            )

        project.add_cost.assert_called_once_with("elevenlabs", 0.11)
        project.mark_progress.assert_called_once_with(
            workflow_module.ProgressStage.ASR_COMPLETED
        )
        convert_file.assert_not_called()
        gemini_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
