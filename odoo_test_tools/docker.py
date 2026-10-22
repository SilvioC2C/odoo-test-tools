"""Docker Compose helpers."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from .exceptions import OdooProcessError
from .utils import die, run
from .versions import COMPOSEFILE_TEMPLATE, get_config

TTY_FLAGS = ["-it"] if sys.stdin.isatty() else []


def build_odoo(composefile: Path, extra_docker_args: list[str] | None = None):
    """Build every service defined by the project Compose file."""
    run(["docker", "compose", "-f", str(composefile), "build", *(extra_docker_args or [])])


def run_odoo(
    composefile: Path,
    odoo_cmd: list[str],
    *,
    publish_ports: bool = False,
    extra_docker_args: list[str] | None = None,
    input_text: str | None = None,
) -> int:
    """Run ``docker compose run --rm [--service-ports] [extra] odoo <cmd>``.

    Returns the subprocess exit code.
    """
    tty_flags = TTY_FLAGS if input_text is None else ["-T"]
    cmd = ["docker", "compose", "-f", str(composefile), "run", "--rm", *tty_flags]
    if publish_ports:
        cmd.append("--service-ports")
    cmd.extend(extra_docker_args or [])
    cmd.append("odoo")
    cmd.extend(odoo_cmd)
    res = run(
        cmd,
        check=False,
        stdout=sys.stdout,
        stderr=sys.stderr,
        **({"input": input_text, "text": True} if input_text is not None else {"stdin": sys.stdin})
    )
    if code := res.returncode:
        raise OdooProcessError(code, cmd, res.stdout, res.stderr)
    return 0


def compose_down(composefile: Path, *, remove_volumes: bool = False, remove_images: bool = False):
    """Tear down the compose project, optionally removing volumes and images"""
    cmd = ["docker", "compose", "-f", str(composefile), "down", "--remove-orphans"]
    if remove_volumes:
        cmd.append("--volumes")
    if remove_images:
        cmd += ["--rmi", "local"]
    run(cmd, check=False)


def ensure_db_service_up(composefile: Path, extra_args: list[str] | None = None):
    """Starts (or verify) the ``db`` service and wait until its healthcheck passes.

    On failure the container log is printed before exiting.
    """
    cmd = [
        "docker", "compose", "-f", str(composefile),
        "up", "-d", "--wait",
        *(extra_args or []),
        "db",
    ]
    result = run(cmd, check=False)
    retcode = result.returncode
    if retcode != 0:
        run(["docker", "compose", "-f", str(composefile), "logs", "db"], check=False)
        die("Failed to start the db service — see logs above.", code=retcode)


def ensure_db_service_down(
    composefile: Path,
    *,
    remove_container: bool = False,
    remove_volumes: bool = False,
    remove_images: bool = False,
) -> None:
    """Stop the ``db`` service and optionally remove the Compose project.

    Removing volumes or images tears down the whole Compose project. On
    failure the container log is printed before exiting.
    """
    if remove_volumes or remove_images:
        cmd = ["docker", "compose", "-f", str(composefile), "down", "--remove-orphans"]
        if remove_volumes:
            cmd.append("--volumes")
        if remove_images:
            cmd.extend(["--rmi", "local"])
    else:
        cmd = ["docker", "compose", "-f", str(composefile), "stop", "db"]

    result = run(cmd, check=False)
    if result.returncode != 0:
        run(["docker", "compose", "-f", str(composefile), "logs", "db"], check=False)
        die("Failed to stop the db service — see logs above.", code=result.returncode)

    if remove_container and not (remove_volumes or remove_images):
        cmd = ["docker", "compose", "-f", str(composefile), "rm", "--force", "db"]
        result = run(cmd, check=False)
        if result.returncode != 0:
            run(["docker", "compose", "-f", str(composefile), "logs", "db"], check=False)
            die("Failed to remove the db service — see logs above.", code=result.returncode)


# -- Templates -----------------------------------------------------------------

ODOO_CFG_TEMPLATE = textwrap.dedent(
    """
    [options]
    db_host = db
    db_port = {pg_container_port}
    db_user = odoo
    db_password = odoo
    addons_path =
        {addons_path}
    """
).lstrip()


# -- Generators ----------------------------------------------------------------

def generate_dockerfile(path: Path, version: str) -> None:
    """Write a minimal Dockerfile that extends the official Odoo image."""
    cfg = get_config(version)
    path.write_text(
        cfg.dockerfile_template.format(version=version, pip_cmd=cfg.pip_cmd),
        encoding="utf-8",
    )


def generate_composefile(
    path: Path,
    version: str,
    work_dir: Path,
    dockerfile: Path,
    mounts: dict[str, Path],
    odoo_port: str,
    pg_host_port: str,
    pg_container_port: str,
) -> None:
    """
    Write a docker-compose.yml that mounts all collected repos and the
    generated ``odoo.cfg``.
    """
    cfg = get_config(version)
    version_id = version.replace(".", "_")
    odoo_cfg_host = work_dir / "odoo.cfg"

    # 10-space indent: services(2) + service(2) + volumes(2) + list item(4)
    repo_lines = "\n".join(
        f"      - {host}:{container}"
        for container, host in mounts.items()
    )
    volumes_block = (
        repo_lines
        + f"\n      - {odoo_cfg_host}:/etc/odoo/odoo.cfg:ro"
    )

    path.write_text(
        COMPOSEFILE_TEMPLATE.format(
            version=version,
            version_id=version_id,
            work_dir=work_dir,
            dockerfile=dockerfile,
            volumes_block=volumes_block,
            odoo_port=odoo_port,
            pg_host_port=pg_host_port,
            pg_container_port=pg_container_port,
            postgres_image=cfg.postgres_image,
        ),
        encoding="utf-8",
    )


def generate_odoo_cfg(
    path: Path,
    addons_path: str,
    pg_container_port: str,
) -> None:
    """Write the ``odoo.cfg`` used by ``pytest-odoo`` inside the container."""
    path.write_text(
        ODOO_CFG_TEMPLATE.format(
            addons_path=",\n    ".join(addons_path.split(",")),
            pg_container_port=pg_container_port,
        ),
        encoding="utf-8",
    )
