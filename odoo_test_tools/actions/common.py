"""Shared action helpers."""

from __future__ import annotations

from pathlib import Path

from ..docker import ensure_db_service_up
from ..postgres import db_exists, get_installed_modules
from ..console import die
from ..utils import run


def odoo_base_cmd(
    db: str,
    extra_odoo_args: list[str],
    test_mode: bool = False,
    use_shell: bool = False,
) -> list[str]:
    """Return the common Odoo CLI options for a project database."""
    cmd = ["/opt/venv/bin/python"]
    if test_mode:
        cmd += [
            "-m", "pytest", "--odoo-config=/etc/odoo/odoo.cfg", f"--odoo-database={db}",
        ]
    else:
        cmd.append("/usr/bin/odoo")
        if use_shell:
            cmd.append("shell")
        cmd.extend(["--config=/etc/odoo/odoo.cfg", f"--database={db}"])
    return cmd + list(extra_odoo_args or [])

def _require_db(composefile: Path, db: str, extra_docker_args: list[str]) -> None:
    ensure_db_service_up(composefile, extra_docker_args)
    if not db_exists(composefile, db, extra_docker_args):
        die(f"Database '{db}' does not exist.")

def _db_service_running(composefile: Path, extra_docker_args: list[str]) -> bool:
    result = run(
        [
            "docker", "compose", "-f", str(composefile), *extra_docker_args,
            "ps", "--status", "running", "-q", "db",
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        die(
            f"Could not inspect the db service: {result.stderr.strip()}",
            code=result.returncode,
        )
    return bool(result.stdout.strip())

def _require_installed_modules(
    composefile: Path,
    db: str,
    modules: list[str],
    extra_docker_args: list[str],
    extra_pg_args: list[str],
) -> None:
    installed = get_installed_modules(composefile, db, extra_docker_args, extra_pg_args)
    missing = [module for module in modules if module not in installed]
    if missing:
        die(f"Module(s) not installed in database '{db}': {', '.join(missing)}")
