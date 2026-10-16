"""Remove a project directory."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..console import die
from ..utils import run
from .rm import action_rm
from .stop import action_stop

def action_deinit(
    *,
    work_dir: Path,
    composefile: Path,
    force: bool = False,
    extra_docker_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    if not work_dir.is_dir():
        return die(f"Project directory '{work_dir}' does not exist.")
    if force:
        if composefile.is_file():
            result = action_stop(
                composefile=composefile,
                extra_docker_args=extra_docker_args,
            )
            if result:
                return result
            result = action_rm(
                composefile=composefile,
                extra_docker_args=extra_docker_args,
            )
            if result:
                return result
    elif composefile.is_file():
        result = run(
            ["docker", "compose", "-f", str(composefile), "ps", "-a", "-q"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            return result.returncode
        if result.stdout.strip():
            return die("Project containers must be stopped and deleted before 'deinit'; use --force.")
    shutil.rmtree(work_dir)
    return 0
