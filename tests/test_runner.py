import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from odoo_test_tools.defaults import ODOO_VERSION_FILE_NAME, WORK_DIR_NAME
from odoo_test_tools import runner


class RunnerTests(unittest.TestCase):
    @staticmethod
    def _args(root: Path, action: str = "init", **overrides):
        values = {
            "root_path": root,
            "action": action,
            "odoo_version": "17.0",
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
            (root / "odoo" / "odoo" / "base").mkdir(parents=True)
            (root / "odoo" / "odoo" / "base" / "__manifest__.py").touch(exist_ok=True)
            addon = root / "oca" / "sale-workflow"
            addon.mkdir(parents=True)
            (addon / "dummy_module").mkdir(parents=True)
            (addon / "dummy_module" / "__manifest__.py").touch(exist_ok=True)
            (addon / "requirements.txt").write_text("requests\n", encoding="utf-8")
            args = self._args(root)

            with patch.object(runner, "parse_args", return_value=(args, {})):
                result = runner.run()

            project = root / WORK_DIR_NAME / "17.0"
            self.assertEqual(result, 0)
            self.assertTrue((project / "docker-compose.yml").is_file())
            self.assertTrue((project / "Dockerfile").is_file())
            self.assertTrue((project / "odoo.cfg").is_file())
            self.assertEqual(
                (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).read_text(),
                "17.0",
            )
            self.assertEqual((project / "requirements.txt").read_text(), "requests")
            default_compose = (project / "docker-compose.yml").read_text()
            self.assertIn(str(addon), default_compose)
            self.assertIn("pgdata_17_0:/var/lib/postgresql/data", default_compose)
            self.assertIn("odoo_data_17_0:/var/lib/odoo", default_compose)

            named_args = self._args(root, name="custom")
            with patch.object(runner, "parse_args", return_value=(named_args, {})):
                result = runner.run()

            named_compose = (root / WORK_DIR_NAME / "custom" / "docker-compose.yml")
            self.assertEqual(result, 0)
            self.assertIn(
                "pgdata_17_0_custom:/var/lib/postgresql/data",
                named_compose.read_text(),
            )
            self.assertIn(
                "odoo_data_17_0_custom:/var/lib/odoo",
                named_compose.read_text(),
            )

    def test_build_dispatches_for_initialized_named_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / WORK_DIR_NAME / "custom"
            project.mkdir(parents=True)
            (project / "docker-compose.yml").touch()
            (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).write_text("17.0")
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

    def test_build_infers_default_project_name_from_version_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / WORK_DIR_NAME / "17.0"
            project.mkdir(parents=True)
            (project / "docker-compose.yml").touch()
            (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).write_text("17.0")
            args = self._args(root, "build")
            action = Mock(return_value=0)
            extra = {"docker": [], "odoo": [], "pytest": [], "pg": []}
            with patch.object(runner, "parse_args", return_value=(args, extra)), \
                    patch.dict(runner.ACTIONS_MAP, {"build": action}):
                result = runner.run()

            self.assertEqual(result, 0)
            action.assert_called_once_with(
                composefile=project / "docker-compose.yml",
                extra_docker_args=[],
            )

    def test_project_without_version_marker_is_not_initialized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / WORK_DIR_NAME / "17.0"
            project.mkdir(parents=True)
            (project / "docker-compose.yml").touch()
            args = self._args(root, "build")
            extra = {"docker": [], "odoo": [], "pytest": [], "pg": []}
            with patch.object(runner, "parse_args", return_value=(args, extra)):
                with self.assertRaises(SystemExit):
                    runner.run()

    def test_database_action_can_keep_db_service_running(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / WORK_DIR_NAME / "17.0"
            project.mkdir(parents=True)
            (project / "docker-compose.yml").touch()
            (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).write_text("17.0")
            args = self._args(root, "createdb", keep_db_service=True)
            action = Mock(return_value=0)
            extra = {"docker": [], "odoo": [], "pytest": [], "pg": []}
            with patch.object(runner, "parse_args", return_value=(args, extra)), \
                    patch.dict(runner.ACTIONS_MAP, {"createdb": action}), \
                    patch.object(runner, "ensure_db_service_down") as stop_db:
                result = runner.run()

            self.assertEqual(result, 0)
            self.assertTrue(action.call_args.kwargs["keep_db_service"])
            stop_db.assert_not_called()

    def test_repo_update_dispatches_branch_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._args(
                root,
                "repo-update",
                path_pos=Path("OCA/sale"),
                path_opt=None,
                branch_pos="17.0",
                branch_opt=None,
                remote="upstream",
            )
            action = Mock(return_value=0)
            with patch.object(runner, "parse_args", return_value=(args, {})), \
                    patch.dict(runner.ACTIONS_MAP, {"repo-update": action}):
                result = runner.run()

            self.assertEqual(result, 0)
            action.assert_called_once_with(
                root=root,
                path=Path("OCA/sale"),
                remote="upstream",
                branch="17.0",
            )

    def test_init_rejects_a_version_that_conflicts_with_shared_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / WORK_DIR_NAME).mkdir()
            (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).write_text("16.0")
            (root / "odoo" / "odoo").mkdir(parents=True)
            args = self._args(root, odoo_version="17.0")
            with patch.object(runner, "parse_args", return_value=(args, {})):
                with self.assertRaises(SystemExit):
                    runner.run()
            self.assertFalse((root / WORK_DIR_NAME / "17.0").exists())


if __name__ == "__main__":
    unittest.main()
