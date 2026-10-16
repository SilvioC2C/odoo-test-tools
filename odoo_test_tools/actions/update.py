"""Update installed modules."""

from __future__ import annotations

from pathlib import Path

from ..docker import run_odoo
from .common import _require_db, _require_installed_modules, odoo_base_cmd

def action_update(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    extra_pg_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    _require_installed_modules(composefile, db, modules, extra_docker_args, extra_pg_args)
    cmd = odoo_base_cmd(db, extra_odoo_args)
    cmd += ["--update=" + ",".join(modules), "--stop-after-init"]
    return run_odoo(composefile, cmd, extra_docker_args=extra_docker_args)
