"""Shared constants and low-level helpers."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from .console import console, die


def copy_source_file(source: Path, target: Path, label: str) -> None:
    if not source.is_file():
        die(f"{label} '{source}' does not exist or is not a file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)


def run(
    cmd: list[str],
    /,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Print and execute a subprocess command."""
    console.print(f"[bold blue]▶[/bold blue] [dim]{' '.join(str(a) for a in cmd)}[/dim]")
    if not console.verbose and not kwargs.get("capture_output", False):
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    kwargs.setdefault("check", True)  # By default, fail on error
    return subprocess.run(cmd, **kwargs)
