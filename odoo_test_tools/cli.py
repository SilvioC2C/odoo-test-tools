"""Command-line argument parsing."""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from . import __version__
from .defaults import ODOO_PORT, ODOO_VERSION_FILE, PG_PORT, ROOT
from .versions import SUPPORTED_VERSIONS


class _PrefixedArgs:
    """Extract and unprefix arguments intended for a downstream command."""

    def __init__(self, prefix: str, *, reserved: set[str] | None = None) -> None:
        self.prefix = f"--{prefix}"
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
            if not arg.startswith(f"{self.prefix}-") or is_reserved:
                remaining.append(arg)
                i += 1
                continue

            stripped = arg[len(self.prefix):]
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


def _add_db_and_addons(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", metavar="NAME", help="Database name")
    parser.add_argument(
        "--addons",
        dest="addons_opt",
        nargs="+",
        metavar="MODULE",
        help="Comma-separated or space-separated Odoo module names",
    )
    parser.add_argument(
        "addons_pos",
        nargs="*",
        metavar="MODULE",
        help="Modules to process (comma-separated or space-separated)",
    )


def _add_keep_db_service(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--keep-db-service", action="store_true",
        help="Leave the database service running after the action",
    )


def parse_args() -> tuple[argparse.Namespace, dict[str, list[str]]]:
    """Parse argv and return its action-specific options and forwarded arguments."""
    argv = sys.argv[1:]
    if "--version" in argv:
        print(f"odoo-test-tools {__version__}")
        raise SystemExit(0)

    docker_args = _PrefixedArgs("docker")
    odoo_args = _PrefixedArgs(
        "odoo",
        reserved={"--odoo-port", "--odoo-cfg-path", "--odoo-version"},
    )
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
              --docker-<flag>   Docker Compose (e.g. --docker--progress=plain)
              --odoo-<flag>     Odoo (e.g. --odoo--log-level=debug)
              --pg-<flag>       PostgreSQL commands (e.g. --pg-v)
              --pytest-<flag>   pytest (e.g. --pytest-k=test_sale)
        """),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
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
        "--root-path", type=Path, default=ROOT, metavar="PATH",
        help=f"Project root (default: {ROOT})",
    )
    name_arg_default = "the provided Odoo version"
    if ODOO_VERSION_FILE.exists():
        with ODOO_VERSION_FILE.open("r") as f:
            name_arg_default = f.read().strip()
    common.add_argument(
        "--name", metavar="NAME",
        help=f"Project name (defaults to {name_arg_default})",
    )

    actions = parser.add_subparsers(dest="action", required=True)

    init = actions.add_parser("init", parents=[common], help="Initialize a project")
    init.add_argument(
        "odoo_version_pos",
        nargs="?",
        choices=sorted(SUPPORTED_VERSIONS),
        metavar="VERSION",
        help="Odoo version to initialize",
    )
    init.add_argument(
        "--odoo-version",
        dest="odoo_version_opt",
        choices=sorted(SUPPORTED_VERSIONS),
        help="Odoo version to initialize",
    )
    init.add_argument("--no-enterprise", action="store_true")
    init.add_argument("--composefile-path", type=Path, metavar="PATH")
    init.add_argument("--dockerfile-path", type=Path, metavar="PATH")
    init.add_argument("--odoo-cfg-path", type=Path, metavar="PATH")
    init.add_argument("--requirements-path", type=Path, metavar="PATH")
    init.add_argument("--exclude-addons-paths", type=Path, nargs="+", metavar="ORG/REPO")
    init.add_argument("--restrict-addons-paths", type=Path, nargs="+", metavar="ORG/REPO")
    init.add_argument("--odoo-port", default=ODOO_PORT, metavar="[HOST:]CONTAINER")
    init.add_argument("--pg-port", default=PG_PORT, metavar="[HOST:]CONTAINER")

    actions.add_parser("build", parents=[common], help="Build project services")

    createdb = actions.add_parser("createdb", parents=[common], help="Create a database")
    _add_db_and_addons(createdb)
    _add_keep_db_service(createdb)

    for action_name in ("install", "update", "uninstall", "test"):
        action_parser = actions.add_parser(
            action_name, parents=[common], help=f"{action_name.capitalize()} modules",
        )
        _add_db_and_addons(action_parser)
        _add_keep_db_service(action_parser)

    ui = actions.add_parser("ui", parents=[common], help="Start an interactive Odoo instance")
    ui.add_argument("--db", metavar="NAME", help="Database name")
    ui.add_argument("--odoo-port", default=ODOO_PORT, metavar="PORT")
    _add_keep_db_service(ui)

    dropdb = actions.add_parser("dropdb", parents=[common], help="Drop a database")
    dropdb.add_argument("--db", metavar="NAME", help="Database name")
    _add_keep_db_service(dropdb)

    actions.add_parser("stop", parents=[common], help="Stop project containers")

    drop = actions.add_parser("rm", parents=[common], help="Remove stopped containers")
    drop.add_argument("--db", dest="db", action="store_true", default=None, help="Select only the DB service")
    drop.add_argument("--odoo", dest="odoo", action="store_true", default=None, help="Select only the Odoo service")
    drop.add_argument("--images", action="store_true", help="Also remove project images")
    drop.add_argument("--volumes", action="store_true", help="Also remove project volumes")
    drop.add_argument("--force", action="store_true", help="Stop selected containers before removing them")

    deinit = actions.add_parser("deinit", parents=[common], help="Remove the project directory")
    deinit.add_argument("--force", action="store_true", help="Stop and remove containers first")

    repo_add = actions.add_parser("repo-add", parents=[common], help="Clone a repository")
    repo_add.add_argument("url_pos", nargs="?", metavar="URL")
    repo_add.add_argument("branch_pos", nargs="?", metavar="BRANCH")
    repo_add.add_argument("--url", dest="url_opt", metavar="URL")
    repo_add.add_argument("--branch", dest="branch_opt", metavar="BRANCH")
    repo_add.add_argument(
        "--init", action="store_true",
        help="Add the repository to the selected project's addons",
    )

    repo_checkout = actions.add_parser(
        "repo-checkout", parents=[common], help="Switch a repository to a ref",
    )
    repo_checkout.add_argument("path_pos", nargs="?", type=Path, metavar="PATH")
    repo_checkout.add_argument("ref_pos", nargs="?", metavar="REF")
    repo_checkout.add_argument("--path", dest="path_opt", type=Path, metavar="PATH")
    repo_checkout.add_argument("--ref", dest="ref_opt", metavar="REF")

    repo_update = actions.add_parser(
        "repo-update", parents=[common], help="Update a repository",
    )
    repo_update.add_argument("path_pos", nargs="?", type=Path, metavar="PATH")
    repo_update.add_argument("branch_pos", nargs="?", metavar="BRANCH")
    repo_update.add_argument("--path", dest="path_opt", type=Path, metavar="PATH")
    repo_update.add_argument("--branch", dest="branch_opt", metavar="BRANCH")
    repo_update.add_argument("--remote", default="origin", metavar="REMOTE")

    repo_rm = actions.add_parser("repo-rm", parents=[common], help="Remove a repository")
    repo_rm.add_argument("path_pos", nargs="?", type=Path, metavar="PATH")
    repo_rm.add_argument("--path", dest="path_opt", type=Path, metavar="PATH")
    repo_rm.add_argument(
        "--init", action="store_true",
        help="Remove the repository from the selected project's addons",
    )

    args = parser.parse_args(argv)
    if args.action == "init":
        if args.odoo_version_pos and args.odoo_version_opt:
            parser.error("Pass the Odoo version either positionally or by --odoo-version.")
        args.odoo_version = args.odoo_version_opt or args.odoo_version_pos
        if not args.odoo_version:
            parser.error("'init' requires an Odoo version.")

    if hasattr(args, "addons_pos"):
        if args.addons_pos and args.addons_opt:
            parser.error("Pass modules either positionally or by --addons.")
        args.addons = args.addons_opt or args.addons_pos
        if args.action in {"install", "update", "uninstall", "test"} and not args.addons:
            parser.error(f"'{args.action}' requires modules (positional or with --addons).")

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
