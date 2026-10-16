"""Create a project database."""

from __future__ import annotations

from pathlib import Path

from ..docker import ensure_db_service_up, run_odoo
from ..postgres import db_exists
from ..console import console, die
from ..utils import run
from .common import _db_service_running, odoo_base_cmd

def action_createdb(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    keep_db_service: bool = False,
    **kwargs,  # keep for compatibility,
) -> int:
    started_here = not _db_service_running(composefile, extra_docker_args)
    ensure_db_service_up(composefile, extra_docker_args)
    try:
        if db_exists(composefile, db, extra_docker_args):
            return die(f"Database '{db}' already exists.")
        modules = sorted(modules or ["base", "web"])
        console.print(f"[bold green]▶ createdb:[/bold green] creating '{db}' with {', '.join(modules)}")
        cmd = odoo_base_cmd(db, extra_odoo_args)
        cmd += [f"--init={','.join(modules)}", "--stop-after-init"]
        return run_odoo(composefile, cmd, extra_docker_args=extra_docker_args)
    finally:
        if started_here and not keep_db_service:
            run(["docker", "compose", "-f", str(composefile), "stop", *extra_docker_args, "db"])
