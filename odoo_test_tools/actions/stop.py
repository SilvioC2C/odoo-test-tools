"""Stop project containers."""

from __future__ import annotations

from pathlib import Path

from ..utils import run

def action_stop(
    *,
    composefile: Path,
    extra_docker_args: list[str],
    **kwargs,  # keep for compatibility
) -> int:
    result = run([
        "docker", "compose", "-f", str(composefile), "stop", *extra_docker_args,
    ], check=False)
    return result.returncode
