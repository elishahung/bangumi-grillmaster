import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import workflow as workflow_module
from services.elevenlabs.asr import ElevenLabsTranscriptionResult


class WorkflowBreakpointTests(unittest.TestCase):
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
        project.audio_path = Path("projects/demo/.asr/audio.opus")
        project.asr_path = Path("projects/demo/.asr/asr.json")
        project.srt_path = Path("projects/demo/video.ja.srt")
        return project

    def test_break_after_asr_completed_stops_before_translation(self):
        project = self._build_project_mock()

        with (
            patch.object(
                workflow_module.Project, "from_source_str", return_value=project
            ),
            patch.object(workflow_module, "ElevenLabsASR") as elevenlabs_cls,
            patch.object(workflow_module, "convert_file") as convert_file,
            patch.object(workflow_module, "Gemini") as gemini_cls,
        ):
            asr = elevenlabs_cls.return_value
            asr.transcribe_to_file.return_value = ElevenLabsTranscriptionResult(
                audio_duration_secs=1800,
                total_cost=0.11,
            )

            workflow_module.process_project(
                "demo",
                break_after=workflow_module.ProgressStage.ASR_COMPLETED,
            )

        asr.transcribe_to_file.assert_called_once_with(
            project.audio_path, project.asr_path
        )
        convert_file.assert_not_called()
        project.mark_progress.assert_called_once_with(
            workflow_module.ProgressStage.ASR_COMPLETED
        )
        gemini_cls.assert_not_called()

    def test_break_after_completed_stage_stops_on_resumed_project(self):
        project = self._build_project_mock()
        project.is_asr_completed = True

        with (
            patch.object(
                workflow_module.Project, "from_source_str", return_value=project
            ),
            patch.object(workflow_module, "ElevenLabsASR") as elevenlabs_cls,
            patch.object(workflow_module, "convert_file") as convert_file,
            patch.object(workflow_module, "Gemini") as gemini_cls,
        ):
            workflow_module.process_project(
                "demo",
                break_after=workflow_module.ProgressStage.ASR_COMPLETED,
            )

        elevenlabs_cls.assert_not_called()
        convert_file.assert_not_called()
        project.mark_progress.assert_not_called()
        gemini_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
