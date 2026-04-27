import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import project as project_module
from project import Project


class ProjectTests(unittest.TestCase):
    def _make_temp_dir(self) -> Path:
        base = Path(__file__).resolve().parents[1] / "tmp_test_artifacts"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "tmp_project"
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
            project.add_cost("elevenlabs", 2.0)

            persisted = json.loads(
                project.json_path.read_text(encoding="utf-8")
            )

        self.assertEqual(project.total_cost, 4.0)
        self.assertEqual(project.service_costs["gemini"], 2.0)
        self.assertEqual(project.service_costs["elevenlabs"], 2.0)
        self.assertEqual(persisted["total_cost"], 4.0)
        self.assertEqual(persisted["service_costs"]["gemini"], 2.0)
        self.assertEqual(persisted["service_costs"]["elevenlabs"], 2.0)

    def test_intermediate_paths_use_hidden_cache_dirs(self):
        root = self._make_temp_dir()
        with patch.object(project_module, "PROJECT_ROOT_NAME", str(root)):
            project = Project(id="layout-project", name="demo")

            self.assertEqual(
                project.audio_path,
                root / "layout-project" / ".asr" / "audio.opus",
            )
            self.assertEqual(
                project.asr_path,
                root / "layout-project" / ".asr" / "asr.json",
            )
            self.assertEqual(
                project.pre_pass_path,
                root / "layout-project" / ".pre_pass" / "pre_pass.json",
            )


if __name__ == "__main__":
    unittest.main()
