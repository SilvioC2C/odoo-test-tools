import tempfile
import unittest
from pathlib import Path

from odoo_test_tools.defaults import (
    extn_src_container_path,
    odoo_ent_container_path,
    odoo_src_container_path,
)
from odoo_test_tools.repos import build_addons_path, collect_repos, find_module_paths


class RepositoryTests(unittest.TestCase):
    def test_collects_matching_repositories_and_can_skip_enterprise(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [
                root / "odoo" / "odoo" / "17.0",
                root / "odoo" / "enterprise" / "17.0",
                root / "OCA" / "sale-workflow" / "17.0",
                root / "OCA" / "stock-logistics" / "16.0",
            ]
            for path in paths:
                path.mkdir(parents=True)

            mounts = collect_repos(root, root / ".odoo-test-tools", "17.0", include_enterprise=False)

        self.assertEqual(mounts[str(odoo_src_container_path)], paths[0])
        self.assertNotIn(str(odoo_ent_container_path), mounts)
        self.assertEqual(
            mounts[str(extn_src_container_path / "sale-workflow")],
            paths[2],
        )
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
                str(odoo_src_container_path): root / "odoo",
                str(extn_src_container_path / "sale-workflow"): external,
            }

            found, missing = find_module_paths(["sale", "missing"], mounts)

        self.assertEqual(found, {"sale": "/odoo/external-src/sale-workflow/sale"})
        self.assertEqual(missing, ["missing"])


if __name__ == "__main__":
    unittest.main()
