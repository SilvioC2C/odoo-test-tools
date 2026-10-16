"""Remove stopped project containers."""

from __future__ import annotations

from pathlib import Path

from ..console import die
from ..utils import run

def action_rm(
    *,
    composefile: Path,
    odoo: bool = True,
    db_service: bool = True,
    images: bool = False,
    volumes: bool = False,
    force: bool = False,
    extra_docker_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    services = [service for service, selected in (("odoo", odoo), ("db", db_service)) if selected]
    if not services:
        return 0
    base = ["docker", "compose", "-f", str(composefile)]
    status = run(
        [*base, *extra_docker_args, "ps", "--status", "running", "-q", *services],
        capture_output=True, text=True, check=False,
    )
    if status.returncode:
        return status.returncode
    if status.stdout.strip() and not force:
        return die("Selected project containers must be stopped before 'rm'; use --force.")
    if force:
        stopped = run([*base, "stop", *extra_docker_args, *services], check=False)
        if stopped.returncode:
            return stopped.returncode
    cmd = [*base, "down"]
    if images:
        cmd.extend(["--rmi", "local"])
    if volumes:
        cmd.append("--volumes")
    cmd.extend([*extra_docker_args, *services])
    return run(cmd, check=False).returncode
