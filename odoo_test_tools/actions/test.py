"""Run tests for installed modules."""

from __future__ import annotations

from pathlib import Path

from ..docker import run_odoo
from ..repos import find_module_paths
from ..console import die
from .common import _require_db, _require_installed_modules, odoo_base_cmd

def action_test(
    *,
    db: str,
    modules: list[str],
    mounts: dict[str, Path],
    composefile: Path,
    extra_docker_args: list[str],
    extra_pytest_args: list[str],
    extra_pg_args: list[str],
    extra_odoo_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    _require_installed_modules(composefile, db, modules, extra_docker_args, extra_pg_args)
    module_paths, missing = find_module_paths(modules, mounts)
    if missing:
        return die(f"Module(s) not found in any repo: {', '.join(missing)}")
    cmd = ["env", "PYTHONPATH=/odoo/src"]
    cmd += odoo_base_cmd(db, extra_odoo_args, test_mode=True)
    cmd += [
        "-p", "no:cacheprovider", "-s",
        *extra_pytest_args,
        *module_paths.values(),
    ]
    return run_odoo(
        composefile, cmd,
        extra_docker_args=["--entrypoint=", "-e", "PYTHONUNBUFFERED=1"] + extra_docker_args,
    )
