"""PostgreSQL introspection via psql inside the db container."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .utils import run


def psql(
    composefile: Path,
    psql_cmd: list[str],
    *,
    extra_docker_args: list[str] | None = None,
    extra_pg_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a PSQL command inside the ``db`` container."""
    cmd = [
        "docker", "compose", "-f", str(composefile),
        "exec", *(extra_docker_args or []), "db",
        *psql_cmd, *(extra_pg_args or []),
    ]
    return run(cmd, capture_output=True, text=True, check=False)


def query(
    composefile: Path,
    query_str: str,
    *,
    db: str = "postgres",
    extra_docker_args: list[str] | None = None,
    extra_pg_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a SQL statement inside the ``db`` container via ``psql``."""
    return psql(
        composefile,
        ["psql", "-U", "odoo", "-d", db, "-c", query_str],
        extra_docker_args=extra_docker_args,
        extra_pg_args=extra_pg_args,
    )


def db_exists(
    composefile: Path,
    db: str,
    extra_docker_args: list[str],
) -> bool:
    """Return ``True`` if the named database exists in Postgres."""
    result = query(
        composefile,
        f"SELECT 1 FROM pg_database WHERE datname = '{db}';",
        extra_docker_args=extra_docker_args,
    )
    return result.returncode == 0 and "1 row" in result.stdout


def get_installed_modules(
    composefile: Path,
    db: str,
    extra_docker_args: list[str],
    extra_pg_args: list[str],
) -> set[str]:
    """
    Return the set of module names that are ``installed`` in the given DB.

    Returns an empty set if the query fails (e.g. the DB has no Odoo schema
    yet).
    """
    result = query(
        composefile,
        "SELECT name FROM ir_module_module WHERE state = 'installed';",
        db=db,
        extra_docker_args=extra_docker_args,
        extra_pg_args=extra_pg_args,
    )
    if result.returncode != 0:
        return set()

    lines = result.stdout.splitlines()
    # psql tabular output: header line, separator line, data rows..., count line, empty
    # line.
    # Skip the first and last two lines.
    return {line.strip() for line in lines[2:-2] if line.strip()}
