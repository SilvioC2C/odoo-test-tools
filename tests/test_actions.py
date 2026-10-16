import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from odoo_test_tools.actions import createdb, rm, test as test_action, uninstall


class ActionTests(unittest.TestCase):
    @patch("odoo_test_tools.actions.createdb.run_odoo", return_value=0)
    @patch("odoo_test_tools.actions.createdb.db_exists", return_value=False)
    @patch("odoo_test_tools.actions.createdb.ensure_db_service_up")
    @patch("odoo_test_tools.actions.common.run")
    @patch("odoo_test_tools.actions.createdb.run")
    def test_createdb_stops_database_service_only_if_it_started_it(
        self, run, common_run, ensure_db, db_exists, run_odoo,
    ):
        run.return_value = subprocess.CompletedProcess([], 0)
        common_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="", stderr="",
        )
        result = createdb.action_createdb(
            db="db_17_0",
            modules=["base", "web"],
            composefile=Path("/tmp/docker-compose.yml"),
            extra_docker_args=[],
            extra_odoo_args=[],
        )

        self.assertEqual(result, 0)
        ensure_db.assert_called_once()
        run_odoo.assert_called_once()
        self.assertEqual(run.call_args_list[-1].args[0][-2:], ["stop", "db"])
        self.assertIn("--init=base,web", run_odoo.call_args.args[1])

    @patch("odoo_test_tools.actions.createdb.run_odoo", return_value=0)
    @patch("odoo_test_tools.actions.createdb.db_exists", return_value=False)
    @patch("odoo_test_tools.actions.createdb.ensure_db_service_up")
    @patch("odoo_test_tools.actions.common.run")
    @patch("odoo_test_tools.actions.createdb.run")
    def test_createdb_keeps_database_service_when_requested(
        self, run, common_run, ensure_db, db_exists, run_odoo,
    ):
        common_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="", stderr="",
        )
        result = createdb.action_createdb(
            db="db_17_0",
            modules=["base", "web"],
            composefile=Path("/tmp/docker-compose.yml"),
            extra_docker_args=[],
            extra_odoo_args=[],
            keep_db_service=True,
        )

        self.assertEqual(result, 0)
        run.assert_not_called()

    @patch("odoo_test_tools.actions.uninstall.run_odoo", return_value=0)
    @patch("odoo_test_tools.actions.uninstall._require_installed_modules")
    @patch("odoo_test_tools.actions.uninstall._require_db")
    def test_uninstall_uses_odoo_shell_api(self, require_db, require_modules, run_odoo):
        result = uninstall.action_uninstall(
            db="db_17_0",
            modules=["sale", "sale_management"],
            composefile=Path("/tmp/docker-compose.yml"),
            extra_docker_args=[],
            extra_odoo_args=[],
            extra_pg_args=[],
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            run_odoo.call_args.args[1],
            [
                "/opt/venv/bin/python", "/usr/bin/odoo", "shell",
                "--config=/etc/odoo/odoo.cfg", "--database=db_17_0",
                "--stop-after-init",
            ],
        )
        self.assertIn(
            "button_immediate_uninstall()",
            run_odoo.call_args.kwargs["input_text"],
        )
        self.assertIn("env.cr.commit()", run_odoo.call_args.kwargs["input_text"])

    @patch("odoo_test_tools.actions.test.run_odoo", return_value=0)
    @patch("odoo_test_tools.actions.test._require_installed_modules")
    @patch("odoo_test_tools.actions.test._require_db")
    @patch("odoo_test_tools.actions.test.find_module_paths")
    def test_test_uses_pytest_from_odoo_virtualenv(
        self, find_module_paths, require_db, require_modules, run_odoo,
    ):
        find_module_paths.return_value = {"sale": "/odoo/addons/sale"}, []
        result = test_action.action_test(
            db="db_17_0",
            modules=["sale"],
            mounts={},
            composefile=Path("/tmp/docker-compose.yml"),
            extra_docker_args=[],
            extra_pytest_args=["-k", "test_sale"],
            extra_pg_args=[],
            extra_odoo_args=[],
        )

        self.assertEqual(result, 0)
        command = run_odoo.call_args.args[1]
        self.assertEqual(
            command,
            [
                "env", "PYTHONPATH=/odoo/src",
                "/opt/venv/bin/python", "-m", "pytest",
                "--odoo-config=/etc/odoo/odoo.cfg",
                "--odoo-database=db_17_0",
                "-p", "no:cacheprovider",
                "-s", "-k", "test_sale", "/odoo/addons/sale",
            ],
        )

    @patch("odoo_test_tools.actions.rm.run")
    def test_drop_requires_selected_running_services_to_be_stopped(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="container-id\n", stderr="")
        with self.assertRaises(SystemExit) as error:
            rm.action_rm(
                composefile=Path("/tmp/docker-compose.yml"),
                odoo=False,
                db_service=True,
                images=False,
                volumes=False,
                force=False,
                extra_docker_args=[],
            )

        self.assertEqual(error.exception.code, 1)
        self.assertEqual(len(run.call_args_list), 1)
        self.assertEqual(run.call_args.args[0][-2:], ["-q", "db"])

    @patch("odoo_test_tools.actions.rm.run")
    def test_drop_only_removes_requested_service(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0),
        ]
        result = rm.action_rm(
            composefile=Path("/tmp/docker-compose.yml"),
            odoo=False,
            db_service=True,
            images=True,
            volumes=True,
            extra_docker_args=[],
        )

        self.assertEqual(result, 0)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[-1].args[0],
            [
                "docker", "compose", "-f", "/tmp/docker-compose.yml",
                "down", "--rmi", "local", "--volumes", "db",
            ],
        )


if __name__ == "__main__":
    unittest.main()
