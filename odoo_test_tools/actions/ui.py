"""Start an interactive Odoo instance."""

from __future__ import annotations

from pathlib import Path

from ..docker import ensure_db_service_up, run_odoo
from ..postgres import db_exists
from .common import odoo_base_cmd
from .createdb import action_createdb

def action_ui(
    *,
    db: str,
    composefile: Path,
    odoo_port: str,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    keep_db_service: bool = False,
    **kwargs,  # keep for compatibility,
) -> int:
    ensure_db_service_up(composefile, extra_docker_args)
    if not db_exists(composefile, db, extra_docker_args):
        result = action_createdb(
            db=db, modules=["base", "web"],
            composefile=composefile, extra_docker_args=extra_docker_args,
            extra_odoo_args=extra_odoo_args,
            keep_db_service=keep_db_service,
        )
        if result:
            return result
    cmd = odoo_base_cmd(db, extra_odoo_args)
    cmd += ["--http-interface=0.0.0.0", f"--http-port={odoo_port}"]
    return run_odoo(
        composefile, cmd, publish_ports=True, extra_docker_args=extra_docker_args,
    )
