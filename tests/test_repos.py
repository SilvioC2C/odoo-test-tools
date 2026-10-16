import tempfile
import unittest
from pathlib import Path

from odoo_test_tools.defaults import (
    EXTN_SRC_CONTAINER_PATH,
    ODOO_ENT_CONTAINER_PATH,
    ODOO_SRC_CONTAINER_PATH,
    WORK_DIR_NAME,
)
from odoo_test_tools.repos import build_addons_path, collect_repos, find_module_paths


class RepositoryTests(unittest.TestCase):
    def test_collects_matching_repositories_and_can_skip_enterprise(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [
                root / "odoo" / "odoo",
                root / "odoo" / "enterprise",
                root / "OCA" / "sale-workflow",
            ]
            for path in paths:
                dummy_module = path.joinpath("dummy_module")
                dummy_module.mkdir(parents=True)
                dummy_module.joinpath("__manifest__.py").touch(exist_ok=True)

            mounts = collect_repos(
                root, root / WORK_DIR_NAME / "17.0", "17.0",
                exclude_enterprise=True,
            )

        self.assertEqual(mounts[str(ODOO_SRC_CONTAINER_PATH)], paths[0])
        self.assertNotIn(str(ODOO_ENT_CONTAINER_PATH), mounts)
        self.assertEqual(mounts[str(EXTN_SRC_CONTAINER_PATH / "sale-workflow")], paths[2])
        self.assertEqual(
            build_addons_path(mounts),
            "/odoo/src/odoo/addons,/odoo/src/addons,/odoo/external-src/sale-workflow",
        )

    def test_finds_modules_only_in_external_mounts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "sale-workflow"
            (external / "sale").mkdir(parents=True)
            mounts = {
                str(ODOO_SRC_CONTAINER_PATH): root / "odoo",
                str(EXTN_SRC_CONTAINER_PATH / "sale-workflow"): external,
            }

            found, missing = find_module_paths(["sale", "missing"], mounts)

        self.assertEqual(found, {"sale": "/odoo/external-src/sale-workflow/sale"})
        self.assertEqual(missing, ["missing"])


if __name__ == "__main__":
    unittest.main()
