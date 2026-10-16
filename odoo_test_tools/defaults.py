"""Shared constants and low-level helpers."""

from pathlib import Path

# -- Default CLI values ---------------------------------------------------------------

ROOT = Path.cwd()
WORK_DIR_NAME = ".odoo-test-tools"
WORK_DIR = ROOT.joinpath(WORK_DIR_NAME)
ODOO_VERSION_FILE_NAME = "ODOO-VERSION.txt"
ODOO_VERSION_FILE = WORK_DIR.joinpath(ODOO_VERSION_FILE_NAME)
DB_NAME = "odoo_test_tools_db"
ODOO_PORT = "8069"
PG_PORT = "5432"

# -- Container paths ------------------------------------------------------------------

ODOO_SRC_CONTAINER_PATH = Path("/odoo/src")
ODOO_ENT_CONTAINER_PATH = Path("/odoo/enterprise-src")
EXTN_SRC_CONTAINER_PATH = Path("/odoo/external-src")
