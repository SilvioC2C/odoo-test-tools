"""Initialize a project."""

from __future__ import annotations

from pathlib import Path

from ..docker import (generate_composefile, generate_dockerfile, generate_odoo_cfg)
from ..repos import build_addons_path, collect_repos
from ..requirements import generate_requirements_file, merge_requirements
from ..console import console, die
from ..utils import copy_source_file
from ..defaults import ODOO_VERSION_FILE_NAME, WORK_DIR_NAME

def action_init(
    *,
    args,
    root: Path,
    work_dir: Path,
    **kwargs,  # keep for compatibility,
) -> int:
    version_file = root / WORK_DIR_NAME / ODOO_VERSION_FILE_NAME
    if version_file.is_file():
        existing_version = version_file.read_text(encoding="utf-8").strip()
        if existing_version != args.odoo_version:
            return die(
                f"Cannot initialize Odoo {args.odoo_version}: '{version_file}' "
                f"already specifies Odoo {existing_version}."
            )

    work_dir.mkdir(parents=True, exist_ok=True)
    mounts = collect_repos(
        root, work_dir, args.odoo_version,
        exclude_enterprise=args.no_enterprise,
        exclude_addons_paths=args.exclude_addons_paths or [],
        restrict_addons_paths=args.restrict_addons_paths or [],
    )
    if not mounts:
        return die(
            f"No repositories found for Odoo {args.odoo_version} under {root}."
        )
    addons_path = build_addons_path(mounts)

    requirements_file = work_dir / "requirements.txt"
    if args.requirements_path:
        copy_source_file(args.requirements_path, requirements_file, "Requirements file")
    else:
        requirement_paths = [
            repo / "requirements.txt"
            for container_path, repo in mounts.items()
            if not container_path.startswith("/odoo/src")
            and not container_path.startswith("/odoo/enterprise-src")
            and (repo / "requirements.txt").is_file()
        ]
        requirements, errors = merge_requirements(requirement_paths)
        if errors:
            return die("Requirements errors:\n" + "\n\n".join(errors))
        generate_requirements_file(requirements_file, requirements)

    dockerfile = work_dir / "Dockerfile"
    if args.dockerfile_path:
        copy_source_file(args.dockerfile_path, dockerfile, "Dockerfile")
    else:
        generate_dockerfile(dockerfile, args.odoo_version)

    composefile = work_dir / "docker-compose.yml"
    if args.composefile_path:
        copy_source_file(args.composefile_path, composefile, "Compose file")
    else:
        generate_composefile(
            composefile,
            args.odoo_version,
            args.name,
            work_dir,
            dockerfile,
            mounts,
            odoo_port=f"{args.odoo_port_host}:{args.odoo_port_container}",
            pg_host_port=args.pg_port_host,
            pg_container_port=args.pg_port_container,
        )

    odoo_cfg = work_dir / "odoo.cfg"
    if args.odoo_cfg_path:
        copy_source_file(args.odoo_cfg_path, odoo_cfg, "Odoo config")
    else:
        generate_odoo_cfg(odoo_cfg, addons_path, args.pg_port_container)

    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(args.odoo_version, encoding="utf-8")
    console.print(f"[bold green]Project initialized:[/bold green] {work_dir}")
    return 0
