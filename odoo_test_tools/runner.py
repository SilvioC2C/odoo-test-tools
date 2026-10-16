"""Main runner for the Odoo Test Tools CLI."""

from __future__ import annotations

import configparser
from pathlib import Path

from .actions import ACTIONS_MAP
from .cli import parse_args
from .defaults import odoo_ent_container_path, odoo_src_container_path
from .docker import ensure_db_service_down
from .repos import build_addons_path, collect_repos
from .utils import die, set_verbose
from .versions import validate_version


def run() -> int:
    args, extra_args = parse_args()
    set_verbose(getattr(args, "verbose", False))
    try:
        validate_version(args.version)
    except ValueError as exc:
        return die(str(exc))

    root = args.root_path.expanduser().resolve()
    if not (root.exists() and root.is_dir()):
        return die(f"Root path '{root}' does not exist or is not a directory.")
    name = args.name or args.version.replace(".", "")
    if name in ("", ".", "..") or Path(name).name != name:
        return die(f"Invalid project name '{name}': it must be a single directory name.")

    work_dir = root / ".odoo-test-tools" / name
    if args.action == "init":
        return ACTIONS_MAP["init"](
            args=args,
            root=root,
            work_dir=work_dir,
        )

    composefile = work_dir / "docker-compose.yml"
    if not composefile.is_file():
        msg, code = f"Project is not initialized at '{work_dir}'.", 0
        if args.action != "deinit":
            msg += " Run 'init' first."
            code = 1
        return die(msg, code=code)

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

    db_name = args.db if isinstance(args.db, str) else f"db_{args.version.replace('.', '_')}"
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
        mounts = collect_repos(root, work_dir, args.version, include_enterprise=True)
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
            allowed_paths = set(addons_path.split(","))
            community_mount = str(odoo_src_container_path)
            enterprise_mount = str(odoo_ent_container_path)
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
        ensure_db_service_down(composefile)
