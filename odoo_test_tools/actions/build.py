"""Build project services."""

from __future__ import annotations

from pathlib import Path

from ..docker import build_odoo
from ..console import die

def action_build(
    *,
    composefile: Path,
    extra_docker_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    if not composefile.is_file():
        return die("Project is not initialized. Run 'init' first.")
    build_odoo(composefile, extra_docker_args)
    return 0
