"""Shared constants and low-level helpers."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from rich.console import Console


# -- Helpers --------------------------------------------------------------------------

class VerboseConsole(Console):
    """A Rich console that hides non-error output unless verbose mode is enabled."""

    verbose = False

    def print(self, *objects, error: bool = False, **kwargs) -> None:
        if self.verbose or error:
            super().print(*objects, **kwargs)


console = VerboseConsole()


def set_verbose(verbose: bool) -> None:
    console.verbose = verbose


def copy_source_file(source: Path, target: Path, label: str) -> None:
    if not source.is_file():
        die(f"{label} '{source}' does not exist or is not a file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)


def die(msg: str, code: int = 1) -> int:
    """Print an error and exit with the requested status code."""
    if code:
        console.print(msg, style="bold red", error=True)
    else:
        console.print(msg)
    raise SystemExit(code)


def run(
    cmd: list[str],
    /,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Print and execute a subprocess command."""
    console.print(f"[bold blue]▶[/bold blue] [dim]{' '.join(str(a) for a in cmd)}[/dim]")
    kwargs.setdefault("check", True)  # By default, fail on error
    return subprocess.run(cmd, **kwargs)
