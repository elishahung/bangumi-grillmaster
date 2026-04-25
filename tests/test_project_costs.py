import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import project as project_module
import workflow as workflow_module
from project import Project
from services.gemini.errors import GeminiTranslationError, TranslationCostSummary


class ProjectCostTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "tmp_project_costs"
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_legacy_project_loads_with_default_cost_fields(self):
        root = self._make_temp_dir()
        project_id = "legacy-project"
        project_dir = root / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "project.json").write_text(
            json.dumps({"id": project_id, "name": "legacy"}),
            encoding="utf-8",
        )

        with patch.object(project_module, "PROJECT_ROOT_NAME", str(root)):
            loaded = Project.from_source_str(project_id)

        self.assertEqual(loaded.total_cost, 0.0)
        self.assertEqual(loaded.service_costs, {})

    def test_add_cost_updates_project_json_totals(self):
        root = self._make_temp_dir()
        with patch.object(project_module, "PROJECT_ROOT_NAME", str(root)):
            project = Project(id="cost-project", name="demo")
            project.save()

            project.add_cost("gemini", 1.25)
            project.add_cost("gemini", 0.75)
            project.add_cost("fun_asr", 2.0)

            persisted = json.loads(
                project.json_path.read_text(encoding="utf-8")
            )

        self.assertEqual(project.total_cost, 4.0)
        self.assertEqual(project.service_costs["gemini"], 2.0)
        self.assertEqual(project.service_costs["fun_asr"], 2.0)
        self.assertEqual(persisted["total_cost"], 4.0)
        self.assertEqual(persisted["service_costs"]["gemini"], 2.0)
        self.assertEqual(persisted["service_costs"]["fun_asr"], 2.0)


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
        project.is_asr_task_submitted = True
        project.is_asr_completed = True
        project.is_srt_completed = True
        project.is_translated = False
        base = Path("projects/demo")
        project.srt_path = base / "video.ja.srt"
        project.video_path = base / "video.mp4"
        project.audio_path = base / "audio.opus"
        project.translated_path = base / "video.cht.srt"
        project.pre_pass_path = base / "pre_pass.json"
        project.pre_pass_cache_dir = base / "pre_pass"
        project.chunks_cache_dir = base / "chunks"
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
            patch.object(workflow_module.Project, "from_source_str", return_value=project),
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
            failed_chunks=["[chunk 2/2] index 11–20: failed"],
        )

        with (
            patch.object(workflow_module.Project, "from_source_str", return_value=project),
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


if __name__ == "__main__":
    unittest.main()
