import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from odoo_test_tools.actions import repositories
from odoo_test_tools.defaults import ODOO_VERSION_FILE_NAME, WORK_DIR_NAME


class RepositoryActionTests(unittest.TestCase):
    @patch("odoo_test_tools.actions.repositories.run")
    @patch("odoo_test_tools.actions.repositories.shutil.which", return_value=None)
    def test_add_clones_to_org_repo_path_and_adds_project_mount(self, which, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / WORK_DIR_NAME / "17.0"
            project.mkdir(parents=True)
            (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).write_text("17.0")
            (project / "odoo.cfg").write_text(
                "[options]\naddons_path =\n    /odoo/src/addons\n",
            )
            (project / "docker-compose.yml").write_text(
                "services:\n"
                "  odoo:\n"
                "    volumes:\n"
                "          - odoo_data:/var/lib/odoo\n"
                "volumes:\n",
            )

            result = repositories.action_repo_add(
                root=root,
                url="https://github.com/OCA/sale-workflow.git",
                branch="17.0",
                init=True,
            )

            self.assertEqual(result, 0)
            which.assert_called_once_with("git-autoshare-clone")
            run.assert_called_once_with(
                [
                    "git", "clone", "--branch", "17.0", "--",
                    "https://github.com/OCA/sale-workflow.git",
                    str(root / "OCA" / "sale-workflow"),
                ],
                cwd=root,
                check=False,
            )
            self.assertIn(
                "/odoo/external-src/sale-workflow",
                (project / "odoo.cfg").read_text(),
            )
            self.assertIn(
                f"{root / 'OCA' / 'sale-workflow'}:/odoo/external-src/sale-workflow",
                (project / "docker-compose.yml").read_text(),
            )

    @patch("odoo_test_tools.actions.repositories.run")
    @patch(
        "odoo_test_tools.actions.repositories.shutil.which",
        return_value="/user/bin/git-autoshare-clone",
    )
    def test_add_uses_installed_git_autoshare(self, which, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            result = repositories.action_repo_add(
                root=root,
                url="https://github.com/OCA/sale-workflow.git",
                branch="17.0",
            )

        self.assertEqual(result, 0)
        which.assert_called_once_with("git-autoshare-clone")
        self.assertEqual(
            run.call_args.args[0],
            [
                "/user/bin/git-autoshare-clone", "--branch", "17.0", "--",
                "https://github.com/OCA/sale-workflow.git",
                str(root / "OCA" / "sale-workflow"),
            ],
        )

    def test_rm_removes_project_mount_and_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "OCA" / "sale-workflow"
            (repo / ".git").mkdir(parents=True)
            project = root / WORK_DIR_NAME / "17.0"
            project.mkdir(parents=True)
            (root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME).write_text("17.0")
            (project / "odoo.cfg").write_text(
                "[options]\naddons_path = /odoo/src/addons,\n"
                "    /odoo/external-src/sale-workflow\n",
            )
            (project / "docker-compose.yml").write_text(
                "services:\n"
                "  odoo:\n"
                "    volumes:\n"
                f"          - {repo}:/odoo/external-src/sale-workflow\n"
                "volumes:\n",
            )

            result = repositories.action_repo_rm(
                root=root, path=Path("OCA/sale-workflow"), init=True,
            )

            self.assertEqual(result, 0)
            self.assertFalse(repo.exists())
            self.assertNotIn(
                "/odoo/external-src/sale-workflow",
                (project / "odoo.cfg").read_text(),
            )
            self.assertNotIn(str(repo), (project / "docker-compose.yml").read_text())

    @patch("odoo_test_tools.actions.repositories.run")
    def test_checkout_and_update_run_in_the_repository(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, stdout="17.0\n"),
            subprocess.CompletedProcess([], 0),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "OCA" / "sale"
            (repo / ".git").mkdir(parents=True)

            self.assertEqual(
                repositories.action_repo_checkout(
                    root=root, path=Path("OCA/sale"), ref="17.0",
                ),
                0,
            )
            self.assertEqual(
                repositories.action_repo_update(
                    root=root, path=Path("OCA/sale"), remote="upstream",
                ),
                0,
            )

        self.assertEqual(run.call_args_list[0].args[0], ["git", "checkout", "17.0"])
        self.assertEqual(run.call_args_list[0].kwargs["cwd"], repo)
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["git", "branch", "--show-current"],
        )
        self.assertEqual(run.call_args_list[1].kwargs["cwd"], repo)
        self.assertEqual(
            run.call_args_list[2].args[0],
            ["git", "pull", "upstream", "17.0"],
        )
        self.assertEqual(run.call_args_list[2].kwargs["cwd"], repo)

    @patch("odoo_test_tools.actions.repositories.run")
    def test_update_checks_provided_branch(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="17.0\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "OCA" / "sale"
            (repo / ".git").mkdir(parents=True)

            self.assertEqual(
                repositories.action_repo_update(
                    root=root, path=Path("OCA/sale"), branch="17.0",
                ),
                0,
            )

        self.assertEqual(
            run.call_args_list[1].args[0],
            ["git", "pull", "origin", "17.0"],
        )

    @patch("odoo_test_tools.actions.repositories.run")
    def test_update_rejects_mismatched_branch(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="16.0\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "OCA" / "sale"
            (repo / ".git").mkdir(parents=True)

            with self.assertRaises(SystemExit):
                repositories.action_repo_update(
                    root=root, path=Path("OCA/sale"), branch="17.0",
                )

        self.assertEqual(run.call_count, 1)

    @patch("odoo_test_tools.actions.repositories.run")
    def test_update_without_path_updates_all_repositories(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="17.0\n"),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, stdout="main\n"),
            subprocess.CompletedProcess([], 0),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repos = [root / "OCA" / "sale", root / "odoo" / "odoo"]
            for repo in repos:
                (repo / ".git").mkdir(parents=True)
            (root / "not-a-repo").mkdir()

            self.assertEqual(repositories.action_repo_update(root=root), 0)

        self.assertEqual(
            [call.kwargs["cwd"] for call in run.call_args_list if call.args[0][1] == "pull"],
            repos,
        )
        self.assertTrue(
            all(
                call.args[0] == ["git", "pull", "origin", branch]
                for call, branch in zip(
                    [call for call in run.call_args_list if call.args[0][1] == "pull"],
                    ["17.0", "main"],
                )
            )
        )

    def test_repo_paths_cannot_escape_the_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SystemExit):
                repositories.action_repo_checkout(
                    root=root, path=Path("../outside"), ref="main",
                )


if __name__ == "__main__":
    unittest.main()
