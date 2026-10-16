import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from odoo_test_tools.docker import (
    ensure_db_service_down,
    generate_composefile,
    generate_dockerfile,
    generate_odoo_cfg,
    run_odoo,
)
from odoo_test_tools.exceptions import OdooProcessError


class DockerHelperTests(unittest.TestCase):
    @patch("odoo_test_tools.docker.run")
    def test_ensure_db_service_down_stops_database(self, run):
        run.return_value.returncode = 0

        ensure_db_service_down(Path("/tmp/compose.yml"))

        run.assert_called_once_with(
            ["docker", "compose", "-f", "/tmp/compose.yml", "stop", "db"],
            check=False,
        )

    @patch("odoo_test_tools.docker.run")
    def test_ensure_db_service_down_removes_project_volumes_and_images(self, run):
        run.return_value.returncode = 0

        ensure_db_service_down(
            Path("/tmp/compose.yml"),
            remove_container=True,
            remove_volumes=True,
            remove_images=True,
        )

        run.assert_called_once_with(
            [
                "docker", "compose", "-f", "/tmp/compose.yml", "down",
                "--remove-orphans", "--volumes", "--rmi", "local",
            ],
            check=False,
        )

    def test_generates_docker_and_compose_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work_dir = root / ".odoo-test-tools"
            work_dir.mkdir()
            dockerfile = work_dir / "Dockerfile"
            composefile = work_dir / "docker-compose.yml"
            cfg = work_dir / "odoo.cfg"
            mounts = {"/odoo/external-src/sale": root / "sale"}

            generate_dockerfile(dockerfile, "17.0")
            generate_composefile(
                composefile,
                "17.0",
                work_dir,
                dockerfile,
                mounts,
                "8169:8069",
                "5346",
                "5432",
            )
            generate_odoo_cfg(cfg, "/odoo/src/addons,/odoo/external-src/sale", "5432")

            dockerfile_text = dockerfile.read_text()
            compose_text = composefile.read_text()
            cfg_text = cfg.read_text()

        self.assertIn("FROM odoo:17.0", dockerfile_text)
        self.assertIn(f"- {root / 'sale'}:/odoo/external-src/sale", compose_text)
        self.assertIn('ports:\n      - "8169:8069"', compose_text)
        self.assertIn('command: ["postgres", "-p", "5432"]', compose_text)
        self.assertIn("pg_isready -U odoo -p 5432", compose_text)
        self.assertIn("addons_path = /odoo/src/addons,/odoo/external-src/sale", cfg_text)

    @patch("odoo_test_tools.docker.run")
    def test_run_odoo_builds_expected_compose_command(self, run):
        with self.assertRaises(OdooProcessError):
            run_odoo(
                Path("/tmp/compose.yml"),
                ["odoo", "--stop-after-init"],
                publish_ports=True,
                extra_docker_args=["--entrypoint", ""],
            )
        run.assert_called_once_with(
            [
                'docker',
                'compose',
                '-f',
                '/tmp/compose.yml',
                'run',
                '--rm',
                '--service-ports',
                '--entrypoint',
                '',
                'odoo',
                'odoo',
                '--stop-after-init',
            ],
            check=False, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
        )

    @patch("odoo_test_tools.docker.run")
    def test_run_odoo_passes_input_without_allocating_a_tty(self, run):
        run.return_value.returncode = 0
        run_odoo(
            Path("/tmp/compose.yml"),
            ["odoo", "shell"],
            input_text="env.cr.commit()\n",
        )

        self.assertIn("-T", run.call_args.args[0])
        self.assertNotIn("-it", run.call_args.args[0])
        self.assertEqual(
            run.call_args.kwargs,
            {
                "check": False,
                "input": "env.cr.commit()\n",
                "text": True,
                "stdout": sys.stdout,
                "stderr": sys.stderr,
            },
        )


if __name__ == "__main__":
    unittest.main()
