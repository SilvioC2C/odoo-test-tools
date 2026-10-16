"""Drop a project database."""

from __future__ import annotations

from pathlib import Path

from ..postgres import psql
from .common import _require_db

def action_dropdb(
    *,
    db: str,
    composefile: Path,
    extra_docker_args: list[str],
    extra_pg_args: list[str], **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    result = psql(
        composefile, ["dropdb", "-U", "odoo", db],
        extra_docker_args=extra_docker_args, extra_pg_args=extra_pg_args,
    )
    return result.returncode
