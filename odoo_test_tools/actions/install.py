"""Install modules in a project database."""

from __future__ import annotations

from pathlib import Path

from ..docker import ensure_db_service_up, run_odoo
from ..postgres import db_exists, get_installed_modules
from ..console import console
from ..utils import run
from .common import _db_service_running, odoo_base_cmd
from .createdb import action_createdb

def action_install(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    extra_pg_args: list[str],
    keep_db_service: bool = False,
    **kwargs,  # keep for compatibility,
) -> int:
    started_here = not _db_service_running(composefile, extra_docker_args)
    ensure_db_service_up(composefile, extra_docker_args)
    if not db_exists(composefile, db, extra_docker_args):
        try:
            return action_createdb(
                db=db, modules=modules,
                composefile=composefile, extra_docker_args=extra_docker_args,
                extra_odoo_args=extra_odoo_args,
                keep_db_service=keep_db_service,
            )
        finally:
            if started_here and not keep_db_service:
                run(
                    ["docker", "compose", "-f", str(composefile), "stop",
                     *extra_docker_args, "db"],
                )
    installed = get_installed_modules(composefile, db, extra_docker_args, extra_pg_args)
    missing = [module for module in modules if module not in installed]
    if not missing:
        console.print(f"  [green]All requested modules are already installed in '{db}'.[/green]")
        return 0
    cmd = odoo_base_cmd(db, extra_odoo_args)
    cmd += ["--init=" + ",".join(missing), "--stop-after-init"]
    return run_odoo(composefile, cmd, extra_docker_args=extra_docker_args)
