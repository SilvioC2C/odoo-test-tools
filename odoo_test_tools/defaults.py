"""Shared constants and low-level helpers."""

from pathlib import Path

# -- Default CLI values ---------------------------------------------------------------

root = Path.cwd()
dbname = "odoo_test_tools_db"
odoo_port = "8069"
pg_port = "5432"

# -- Container paths ------------------------------------------------------------------

odoo_src_container_path = Path("/odoo/src")
odoo_ent_container_path = Path("/odoo/enterprise-src")
extn_src_container_path = Path("/odoo/external-src")
