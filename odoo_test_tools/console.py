"""Console output helpers."""

from __future__ import annotations

from rich.console import Console


class VerboseConsole(Console):
    """A Rich console that hides non-error output unless verbose mode is enabled."""

    verbose = False

    def print(self, *objects, error: bool = False, **kwargs) -> None:
        if self.verbose or error:
            super().print(*objects, **kwargs)


console = VerboseConsole()


def set_verbose(verbose: bool) -> None:
    console.verbose = verbose


def die(msg: str, code: int = 1) -> int:
    """Print an error and exit with the requested status code."""
    if code:
        console.print(msg, style="bold red", error=True)
    else:
        console.print(msg)
    raise SystemExit(code)
