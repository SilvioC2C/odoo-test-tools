"""Project action implementations."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .docker import (
    build_odoo,
    ensure_db_service_up,
    generate_composefile,
    generate_dockerfile,
    generate_odoo_cfg,
    run_odoo,
)
from .postgres import db_exists, get_installed_modules, psql
from .repos import build_addons_path, collect_repos, find_module_paths
from .requirements import generate_requirements_file, merge_requirements
from .utils import console, copy_source_file, die, run


def odoo_base_cmd(
    db: str,
    extra_odoo_args: list[str],
    test_mode: bool = False,
    use_shell: bool = False,
) -> list[str]:
    """Return the common Odoo CLI options for a project database."""
    cmd = ["/opt/venv/bin/python"]
    if test_mode:
        cmd += [
            "-m", "pytest", "--odoo-config=/etc/odoo/odoo.cfg", f"--odoo-database={db}",
        ]
    else:
        cmd.append("/usr/bin/odoo")
        if use_shell:
            cmd.append("shell")
        cmd.extend(["--config=/etc/odoo/odoo.cfg", f"--database={db}"])
    return cmd + list(extra_odoo_args or [])


def _require_db(composefile: Path, db: str, extra_docker_args: list[str]) -> None:
    ensure_db_service_up(composefile, extra_docker_args)
    if not db_exists(composefile, db, extra_docker_args):
        die(f"Database '{db}' does not exist.")


def _db_service_running(composefile: Path, extra_docker_args: list[str]) -> bool:
    result = run(
        [
            "docker", "compose", "-f", str(composefile), *extra_docker_args,
            "ps", "--status", "running", "-q", "db",
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        die(
            f"Could not inspect the db service: {result.stderr.strip()}",
            code=result.returncode,
        )
    return bool(result.stdout.strip())


def _require_installed_modules(
    composefile: Path,
    db: str,
    modules: list[str],
    extra_docker_args: list[str],
    extra_pg_args: list[str],
) -> None:
    installed = get_installed_modules(composefile, db, extra_docker_args, extra_pg_args)
    missing = [module for module in modules if module not in installed]
    if missing:
        die(f"Module(s) not installed in database '{db}': {', '.join(missing)}")


def action_init(
    *,
    args,
    root: Path,
    work_dir: Path,
    **kwargs,  # keep for compatibility,
) -> int:
    work_dir.mkdir(parents=True, exist_ok=True)
    mounts = collect_repos(
        root, work_dir, args.version,
        exclude_enterprise=args.no_enterprise,
        exclude_addons_paths=args.exclude_addons_paths or [],
        restrict_addons_paths=args.restrict_addons_paths or [],
    )
    if not mounts:
        return die(f"No repositories found for version {args.version} under {root}.")
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
        generate_dockerfile(dockerfile, args.version)

    composefile = work_dir / "docker-compose.yml"
    if args.composefile_path:
        copy_source_file(args.composefile_path, composefile, "Compose file")
    else:
        generate_composefile(
            composefile,
            args.version,
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

    console.print(f"[bold green]Project initialized:[/bold green] {work_dir}")
    return 0


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


def action_createdb(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    started_here = not _db_service_running(composefile, extra_docker_args)
    ensure_db_service_up(composefile, extra_docker_args)
    try:
        if db_exists(composefile, db, extra_docker_args):
            return die(f"Database '{db}' already exists.")
        modules = sorted(modules or ["base", "web"])
        console.print(f"[bold green]▶ createdb:[/bold green] creating '{db}' with {', '.join(modules)}")
        cmd = odoo_base_cmd(db, extra_odoo_args)
        cmd += [f"--init={','.join(modules)}", "--stop-after-init"]
        return run_odoo(composefile, cmd, extra_docker_args=extra_docker_args)
    finally:
        if started_here:
            run(["docker", "compose", "-f", str(composefile), "stop", *extra_docker_args, "db"])


def action_install(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    extra_pg_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    started_here = not _db_service_running(composefile, extra_docker_args)
    ensure_db_service_up(composefile, extra_docker_args)
    if not db_exists(composefile, db, extra_docker_args):
        try:
            return action_createdb(
                db=db, modules=modules,
                composefile=composefile, extra_docker_args=extra_docker_args,
                extra_odoo_args=extra_odoo_args,
            )
        finally:
            if started_here:
                run(
                    ["docker", "compose", "-f", str(composefile), "stop",
                     *extra_docker_args, "db"],
                )
    installed = get_installed_modules(composefile, db, extra_docker_args, extra_pg_args)
    missing = [module for module in modules if module not in installed]
    if not missing:
        console.print(f"  [green]All requested modules are already installed in '{db}'.[/green]")
        return 0
    cmd = odoo_base_cmd(db, extra_odoo_args)
    cmd += ["--init=" + ",".join(missing), "--stop-after-init"]
    return run_odoo(composefile, cmd, extra_docker_args=extra_docker_args)


def action_update(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    extra_pg_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    _require_installed_modules(composefile, db, modules, extra_docker_args, extra_pg_args)
    cmd = odoo_base_cmd(db, extra_odoo_args)
    cmd += ["--update=" + ",".join(modules), "--stop-after-init"]
    return run_odoo(composefile, cmd, extra_docker_args=extra_docker_args)


def action_uninstall(
    *,
    db: str,
    modules: list[str],
    composefile: Path,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    extra_pg_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    _require_installed_modules(composefile, db, modules, extra_docker_args, extra_pg_args)
    cmd = odoo_base_cmd(db, extra_odoo_args, use_shell=True)
    cmd += ["--stop-after-init"]
    script = (
        "env['ir.module.module'].search([('name', 'in', "
        f"{modules!r})]).button_immediate_uninstall()\n"
        "env.cr.commit()\n"
    )
    return run_odoo(
        composefile, cmd,
        extra_docker_args=extra_docker_args,
        input_text=script,
    )


def action_test(
    *,
    db: str,
    modules: list[str],
    mounts: dict[str, Path],
    composefile: Path,
    extra_docker_args: list[str],
    extra_pytest_args: list[str],
    extra_pg_args: list[str],
    extra_odoo_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    _require_installed_modules(composefile, db, modules, extra_docker_args, extra_pg_args)
    module_paths, missing = find_module_paths(modules, mounts)
    if missing:
        return die(f"Module(s) not found in any repo: {', '.join(missing)}")
    cmd = ["env", "PYTHONPATH=/odoo/src"]
    cmd += odoo_base_cmd(db, extra_odoo_args, test_mode=True)
    cmd += [
        "-p", "no:cacheprovider", "-s",
        *extra_pytest_args,
        *module_paths.values(),
    ]
    return run_odoo(
        composefile, cmd,
        extra_docker_args=["--entrypoint=", "-e", "PYTHONUNBUFFERED=1"] + extra_docker_args,
    )


def action_ui(
    *,
    db: str,
    composefile: Path,
    odoo_port: str,
    extra_docker_args: list[str],
    extra_odoo_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    ensure_db_service_up(composefile, extra_docker_args)
    if not db_exists(composefile, db, extra_docker_args):
        result = action_createdb(
            db=db, modules=["base", "web"],
            composefile=composefile, extra_docker_args=extra_docker_args,
            extra_odoo_args=extra_odoo_args,
        )
        if result:
            return result
    cmd = odoo_base_cmd(db, extra_odoo_args)
    cmd += ["--http-interface=0.0.0.0", f"--http-port={odoo_port}"]
    return run_odoo(
        composefile, cmd, publish_ports=True, extra_docker_args=extra_docker_args,
    )


def action_dropdb(
    *,
    db: str,
    composefile: Path,
    extra_docker_args: list[str],
    extra_pg_args: list[str], **kwargs,  # keep for compatibility,
) -> int:
    _require_db(composefile, db, extra_docker_args)
    result = psql(
        composefile, ["dropdb", "-U", "odoo", db],
        extra_docker_args=extra_docker_args, extra_pg_args=extra_pg_args,
    )
    return result.returncode


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


def action_rm(
    *,
    composefile: Path,
    odoo: bool = True,
    db_service: bool = True,
    images: bool = False,
    volumes: bool = False,
    force: bool = False,
    extra_docker_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    services = [service for service, selected in (("odoo", odoo), ("db", db_service)) if selected]
    if not services:
        return 0
    base = ["docker", "compose", "-f", str(composefile)]
    status = run(
        [*base, *extra_docker_args, "ps", "--status", "running", "-q", *services],
        capture_output=True, text=True, check=False,
    )
    if status.returncode:
        return status.returncode
    if status.stdout.strip() and not force:
        return die("Selected project containers must be stopped before 'drop'; use --force.")
    if force:
        stopped = run([*base, "stop", *extra_docker_args, *services], check=False)
        if stopped.returncode:
            return stopped.returncode
    cmd = [*base, "down"]
    if images:
        cmd.extend(["--rmi", "local"])
    if volumes:
        cmd.append("--volumes")
    cmd.extend([*extra_docker_args, *services])
    return run(cmd, check=False).returncode


def action_deinit(
    *,
    work_dir: Path,
    composefile: Path,
    force: bool = False,
    extra_docker_args: list[str],
    **kwargs,  # keep for compatibility,
) -> int:
    if not work_dir.is_dir():
        return die(f"Project directory '{work_dir}' does not exist.")
    if force:
        if composefile.is_file():
            result = action_stop(
                composefile=composefile,
                extra_docker_args=extra_docker_args,
            )
            if result:
                return result
            result = action_rm(
                composefile=composefile,
                extra_docker_args=extra_docker_args,
            )
            if result:
                return result
    elif composefile.is_file():
        result = run(
            ["docker", "compose", "-f", str(composefile), "ps", "-a", "-q"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            return result.returncode
        if result.stdout.strip():
            return die("Project containers must be stopped and deleted before 'deinit'; use --force.")
    shutil.rmtree(work_dir)
    return 0


ACTIONS_MAP: dict[str, Callable] = {
    "init": action_init,
    "build": action_build,
    "createdb": action_createdb,
    "install": action_install,
    "update": action_update,
    "uninstall": action_uninstall,
    "test": action_test,
    "ui": action_ui,
    "dropdb": action_dropdb,
    "stop": action_stop,
    "rm": action_rm,
    "deinit": action_deinit,
}
