"""Command-line argument parsing."""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from .defaults import odoo_port, pg_port, root
from .versions import SUPPORTED_VERSIONS


class _PrefixedArgs:
    """Extract and unprefix arguments intended for a downstream command."""

    def __init__(self, prefix: str, *, reserved: set[str] | None = None) -> None:
        self.prefix = f"--{prefix}-"
        self.reserved = reserved or set()
        self.args: list[str] = []

    def extract(self, argv: list[str]) -> list[str]:
        remaining: list[str] = []
        i = 0
        while i < len(argv):
            arg = argv[i]
            is_reserved = arg in self.reserved or any(
                arg.startswith(f"{reserved}=") for reserved in self.reserved
            )
            if not arg.startswith(self.prefix) or is_reserved:
                remaining.append(arg)
                i += 1
                continue

            stripped = "--" + arg[len(self.prefix):]
            self.args.append(stripped)
            if "=" in stripped:
                i += 1
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                self.args.append(argv[i + 1])
                i += 2
            else:
                i += 1
        return remaining


def _split_port(value: str) -> tuple[str, str]:
    host, separator, container = value.partition(":")
    return (host, container) if separator else (value, value)


def _add_db_and_addons(parser: argparse.ArgumentParser, *, addons_required: bool) -> None:
    parser.add_argument("--db", metavar="NAME", help="Database name")
    parser.add_argument(
        "--addons",
        nargs="+",
        required=addons_required,
        metavar="MODULE",
        help="Comma-separated or space-separated Odoo module names",
    )


def parse_args() -> tuple[argparse.Namespace, dict[str, list[str]]]:
    """Parse argv and return its action-specific options and forwarded arguments."""
    argv = sys.argv[1:]
    docker_args = _PrefixedArgs("docker")
    odoo_args = _PrefixedArgs("odoo", reserved={"--odoo-port", "--odoo-cfg-path"})
    pg_args = _PrefixedArgs("pg", reserved={"--pg-port"})
    pytest_args = _PrefixedArgs("pytest")
    for extractor in (docker_args, odoo_args, pg_args, pytest_args):
        argv = extractor.extract(argv)

    parser = argparse.ArgumentParser(
        prog="odoo-test-tools",
        description="Manage local Odoo development projects via Docker Compose.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Forward arguments to downstream tools with a prefix:
              --docker-<flag>   Docker Compose (e.g. --docker-progress=plain)
              --odoo-<flag>     Odoo (e.g. --odoo-log-level=debug)
              --pg-<flag>       PostgreSQL commands (e.g. --pg-v)
              --pytest-<flag>   pytest (e.g. --pytest-k=test_sale)
        """),
    )
    parser.add_argument(
        "version", choices=sorted(SUPPORTED_VERSIONS), help="Odoo version",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Show informational output",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS,
        help="Show informational output",
    )
    common.add_argument(
        "--root-path", type=Path, default=root, metavar="PATH",
        help=f"Project root (default: {root})",
    )
    common.add_argument(
        "--name", metavar="NAME",
        help="Project name (default: Odoo version without dots)",
    )

    actions = parser.add_subparsers(dest="action", required=True)

    init = actions.add_parser("init", parents=[common], help="Initialize a project")
    init.add_argument("--no-enterprise", action="store_true")
    init.add_argument("--composefile-path", type=Path, metavar="PATH")
    init.add_argument("--dockerfile-path", type=Path, metavar="PATH")
    init.add_argument("--odoo-cfg-path", type=Path, metavar="PATH")
    init.add_argument("--requirements-path", type=Path, metavar="PATH")
    init.add_argument("--exclude-addons-paths", type=Path, nargs="+", metavar="ORG/REPO")
    init.add_argument("--restrict-addons-paths", type=Path, nargs="+", metavar="ORG/REPO")
    init.add_argument("--odoo-port", default=odoo_port, metavar="[HOST:]CONTAINER")
    init.add_argument("--pg-port", default=pg_port, metavar="[HOST:]CONTAINER")

    actions.add_parser("build", parents=[common], help="Build project services")

    createdb = actions.add_parser("createdb", parents=[common], help="Create a database")
    _add_db_and_addons(createdb, addons_required=False)

    for action_name in ("install", "update", "uninstall", "test"):
        action_parser = actions.add_parser(
            action_name, parents=[common], help=f"{action_name.capitalize()} modules",
        )
        _add_db_and_addons(action_parser, addons_required=True)

    ui = actions.add_parser("ui", parents=[common], help="Start an interactive Odoo instance")
    ui.add_argument("--db", metavar="NAME", help="Database name")
    ui.add_argument("--odoo-port", default=odoo_port, metavar="PORT")

    dropdb = actions.add_parser("dropdb", parents=[common], help="Drop a database")
    dropdb.add_argument("--db", metavar="NAME", help="Database name")

    actions.add_parser("stop", parents=[common], help="Stop project containers")

    drop = actions.add_parser("rm", parents=[common], help="Remove stopped containers")
    drop.add_argument("--db", dest="db", action="store_true", default=None, help="Select only the DB service")
    drop.add_argument("--odoo", dest="odoo", action="store_true", default=None, help="Select only the Odoo service")
    drop.add_argument("--images", action="store_true", help="Also remove project images")
    drop.add_argument("--volumes", action="store_true", help="Also remove project volumes")
    drop.add_argument("--force", action="store_true", help="Stop selected containers before removing them")

    deinit = actions.add_parser("deinit", parents=[common], help="Remove the project directory")
    deinit.add_argument("--force", action="store_true", help="Stop and remove containers first")

    args = parser.parse_args(argv)
    if args.action == "init":
        args.odoo_port_host, args.odoo_port_container = _split_port(args.odoo_port)
        args.pg_port_host, args.pg_port_container = _split_port(args.pg_port)

    extra = {
        "docker": docker_args.args,
        "odoo": odoo_args.args,
        "pg": pg_args.args,
        "pytest": pytest_args.args,
    }
    return args, extra
