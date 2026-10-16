import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from odoo_test_tools import runner


class RunnerTests(unittest.TestCase):
    @staticmethod
    def _args(root: Path, action: str = "init", **overrides):
        values = {
            "root_path": root,
            "version": "17.0",
            "action": action,
            "no_enterprise": False,
            "requirements_path": None,
            "dockerfile_path": None,
            "composefile_path": None,
            "odoo_cfg_path": None,
            "exclude_addons_paths": None,
            "restrict_addons_paths": None,
            "name": None,
            "db": None,
            "addons": None,
            "odoo_port_host": "8069",
            "odoo_port_container": "8069",
            "pg_port_host": "5432",
            "pg_port_container": "5432",
            "force": False,
            "images": False,
            "volumes": False,
            "odoo_service": None,
            "db_service": None,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_init_creates_project_scoped_environment_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "odoo" / "odoo" / "17.0").mkdir(parents=True)
            addon = root / "oca" / "sale" / "17.0"
            addon.mkdir(parents=True)
            (addon / "requirements.txt").write_text("requests\n", encoding="utf-8")
            args = self._args(root)

            with patch.object(runner, "parse_args", return_value=(args, {})):
                result = runner.run()

            project = root / ".odoo-test-tools" / "170"
            self.assertEqual(result, 0)
            self.assertTrue((project / "docker-compose.yml").is_file())
            self.assertTrue((project / "Dockerfile").is_file())
            self.assertTrue((project / "odoo.cfg").is_file())
            self.assertEqual((project / "requirements.txt").read_text(), "requests")
            self.assertIn(str(addon), (project / "docker-compose.yml").read_text())

    def test_build_dispatches_for_initialized_named_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / ".odoo-test-tools" / "custom"
            project.mkdir(parents=True)
            (project / "docker-compose.yml").touch()
            args = self._args(root, "build", name="custom")
            action = Mock(return_value=0)
            extra = {"docker": ["--progress=plain"], "odoo": [], "pytest": [], "pg": []}
            with patch.object(runner, "parse_args", return_value=(args, extra)), \
                    patch.dict(runner.ACTIONS_MAP, {"build": action}):
                result = runner.run()

            self.assertEqual(result, 0)
            action.assert_called_once_with(
                composefile=project / "docker-compose.yml",
                extra_docker_args=["--progress=plain"],
            )


if __name__ == "__main__":
    unittest.main()
