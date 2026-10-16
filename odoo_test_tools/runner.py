"""Main runner for the Odoo Test Tools CLI."""

from __future__ import annotations

import configparser
from pathlib import Path

from .actions import ACTIONS_MAP
from .cli import parse_args
from .defaults import (
    ODOO_ENT_CONTAINER_PATH,
    ODOO_SRC_CONTAINER_PATH,
    ODOO_VERSION_FILE_NAME,
    WORK_DIR_NAME,
)
from .docker import ensure_db_service_down
from .repos import build_addons_path, collect_repos
from .console import die, set_verbose
from .versions import validate_version


def _find_project(root: Path, name: str | None) -> tuple[Path, str]:
    work_dir = root / WORK_DIR_NAME
    version_file = work_dir / ODOO_VERSION_FILE_NAME
    if not version_file.is_file():
        return work_dir / (name or ""), ""
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"Cannot read project version file '{version_file}': {exc}") from exc
    try:
        validate_version(version)
    except ValueError as exc:
        raise ValueError(f"Invalid Odoo version in '{version_file}': {exc}") from exc
    return work_dir / (name or version), version


def run() -> int:
    args, extra_args = parse_args()
    set_verbose(getattr(args, "verbose", False))

    root = args.root_path.expanduser().resolve()
    if not (root.exists() and root.is_dir()):
        return die(f"Root path '{root}' does not exist or is not a directory.")

    if args.action == "init":
        version = args.odoo_version
        try:
            validate_version(version)
        except ValueError as exc:
            return die(str(exc))
        name = args.name or version
        if name in ("", ".", "..") or Path(name).name != name:
            return die(f"Invalid project name '{name}': it must be a single directory name.")
        work_dir = root / WORK_DIR_NAME / name
        return ACTIONS_MAP["init"](
            args=args,
            root=root,
            work_dir=work_dir,
        )

    if args.action in {"repo-add", "repo-checkout", "repo-update", "repo-rm"}:
        if args.action == "repo-add":
            url = args.url_opt or args.url_pos
            branch = args.branch_opt or args.branch_pos
            if not url or not branch:
                return die("'repo-add' requires a repository URL and branch.")
            if args.url_opt and args.url_pos or args.branch_opt and args.branch_pos:
                return die("Pass each 'repo-add' URL and branch either positionally or by option.")
            return ACTIONS_MAP[args.action](
                root=root, url=url, branch=branch, name=args.name, init=args.init,
            )
        path = args.path_opt or args.path_pos
        if args.path_opt and args.path_pos:
            return die(f"Pass '{args.action}' repository path either positionally or by --path.")
        if args.action == "repo-checkout":
            if not path:
                return die(f"'repo-checkout' requires a repository path.")
            ref = args.ref_opt or args.ref_pos
            if not ref:
                return die("'repo-checkout' requires a ref.")
            if args.ref_opt and args.ref_pos:
                return die("Pass 'repo-checkout' ref either positionally or by --ref.")
            return ACTIONS_MAP[args.action](root=root, path=path, ref=ref)
        if args.action == "repo-update":
            branch = (
                args.branch_opt
                if args.branch_opt is not None
                else args.branch_pos
            )
            if args.branch_opt is not None and args.branch_pos is not None:
                return die("Pass 'repo-update' branch either positionally or by --branch.")
            return ACTIONS_MAP[args.action](
                root=root, path=path, remote=args.remote, branch=branch,
            )
        return ACTIONS_MAP[args.action](
            root=root, path=path, name=args.name, init=args.init,
        )

    try:
        work_dir, version = _find_project(root, args.name)
        if not version:
            return die(f"Project is not initialized under '{root}'. Run 'init' first.")
        validate_version(version)
    except ValueError as exc:
        return die(str(exc))

    composefile = work_dir / "docker-compose.yml"
    if args.action == "build":
        return ACTIONS_MAP["build"](
            composefile=composefile,
            extra_docker_args=extra_args["docker"],
        )
    if args.action == "stop":
        return ACTIONS_MAP["stop"](
            composefile=composefile,
            extra_docker_args=extra_args["docker"],
        )
    if args.action == "rm":
        return ACTIONS_MAP["rm"](
            composefile=composefile,
            odoo=True if args.odoo is None else args.odoo,
            db_service=True if args.db is None else args.db,
            images=args.images,
            volumes=args.volumes,
            force=args.force,
            extra_docker_args=extra_args["docker"],
        )
    if args.action == "deinit":
        return ACTIONS_MAP["deinit"](
            work_dir=work_dir, composefile=composefile, force=args.force,
            extra_docker_args=extra_args["docker"],
        )

    db_name = args.db if isinstance(args.db, str) else f"db_{version.replace('.', '_')}"
    modules = [m for v in getattr(args, "addons", []) or [] for m in v.split(",") if m]
    mounts: dict[str, Path] = {}
    addons_path = ""
    if args.action in {"install", "update", "uninstall"}:
        if not modules:
            return die(f"--addons is required for '{args.action}'.")
    elif args.action == "createdb":
        if not modules:
            modules = ["base", "web"]
    elif args.action == "test":
        if not modules:
            return die(f"--addons is required for 'test'.")
        mounts = collect_repos(root, work_dir, version, exclude_enterprise=False)
        config = configparser.ConfigParser()
        try:
            with (work_dir / "odoo.cfg").open(encoding="utf-8") as cfg_file:
                config.read_file(cfg_file)
            addons_path = config.get(
                "options", "addons_path", fallback=build_addons_path(mounts),
            )
        except (OSError, KeyError, configparser.Error) as exc:
            return die(f"Cannot read project Odoo configuration at '{work_dir / 'odoo.cfg'}': {exc}")
        if addons_path:
            allowed_paths = set(map(str.strip, addons_path.split(",")))
            community_mount = str(ODOO_SRC_CONTAINER_PATH)
            enterprise_mount = str(ODOO_ENT_CONTAINER_PATH)
            mounts = {
                container: host
                for container, host in mounts.items()
                if (
                    container == community_mount
                    and any(path.startswith(community_mount + "/") for path in allowed_paths)
                ) or (
                    container == enterprise_mount and enterprise_mount in allowed_paths
                ) or container in allowed_paths
            }

    action_kwargs = dict(
        db=db_name,
        addons_path=addons_path,
        modules=modules,
        mounts=mounts,
        keep_db_service=getattr(args, "keep_db_service", False),
        composefile=composefile,
        extra_docker_args=extra_args["docker"],
        extra_odoo_args=extra_args["odoo"],
        extra_pytest_args=extra_args["pytest"],
        extra_pg_args=extra_args["pg"],
    )
    if args.action == "ui":
        action_kwargs["odoo_port"] = args.odoo_port
    try:
        return ACTIONS_MAP[args.action](**action_kwargs)
    finally:
        if not action_kwargs["keep_db_service"]:
            ensure_db_service_down(composefile)
