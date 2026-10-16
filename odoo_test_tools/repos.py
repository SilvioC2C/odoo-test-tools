"""Multirepo scanning and addon path utilities."""

from __future__ import annotations

from pathlib import Path

from .defaults import ODOO_ENT_CONTAINER_PATH, EXTN_SRC_CONTAINER_PATH, ODOO_SRC_CONTAINER_PATH
from .console import console, die


def collect_repos(
    root: Path,
    work_dir: Path,
    version: str,
    *,
    exclude_enterprise: bool,
    exclude_addons_paths: list[Path] | None = None,
    restrict_addons_paths: list[Path] | None = None,
) -> dict[str, Path]:
    """
    Scan ``<root>/<org>/<repo>/`` and return
    ``{container_path: host_path}`` for every matching directory.

    Layout:
        odoo/odoo                   → /odoo/src
        odoo/enterprise             → /odoo/enterprise-src
        <org>/<repo>                → /odoo/external-src/<repo>
    """
    def repo_names(paths: list[Path] | None, option: str) -> set[str]:
        names: set[str] = set()
        for path in paths or ():
            value = path.as_posix().strip("/")
            if len(Path(value).parts) != 2 or any(part in ("", ".", "..") for part in Path(value).parts):
                die(f"Invalid {option} value '{path}': expected <org>/<repo>.")
            names.add(value)
        return names

    excluded = repo_names(exclude_addons_paths, "--exclude-addons-paths")
    restricted = repo_names(restrict_addons_paths, "--restrict-addons-paths")
    mounts: dict[str, Path] = {}
    for repo_dir in sorted(p for p in root.glob("*/*") if p.is_dir()):
        if not any(d.joinpath("__manifest__.py").exists() for d in repo_dir.iterdir()):
            continue
        if repo_dir.is_relative_to(work_dir):
            continue
        org = repo_dir.parent.name
        repo = repo_dir.name
        repo_name = f"{org}/{repo}"
        if repo_name != "odoo/odoo" and (
            repo_name in excluded or (restricted and repo_name not in restricted)
        ):
            continue
        elif repo_name == "odoo/odoo":
            container = str(ODOO_SRC_CONTAINER_PATH)
        elif repo_name == "odoo/enterprise":
            if exclude_enterprise:
                console.print(f"  [yellow]↷ skipping odoo/enterprise/{version} (--no-enterprise)[/yellow]")
                continue
            container = str(ODOO_ENT_CONTAINER_PATH)
        else:
            container = f"{EXTN_SRC_CONTAINER_PATH}/{repo}"
        mounts[container] = repo_dir
        console.print(f"  [green]✔[/green] {repo_name}/{version} → {container}")
    return mounts


def build_addons_path(mounts: dict[str, Path]) -> str:
    """Build the comma-separated Odoo ``--addons-path`` value from collected mounts

    Order: CE built-ins → CE addons → Enterprise → external repos.
    """
    parts: list[str] = []
    if str(ODOO_SRC_CONTAINER_PATH) in mounts:
        parts += [
            f"{ODOO_SRC_CONTAINER_PATH}/odoo/addons",
            f"{ODOO_SRC_CONTAINER_PATH}/addons",
        ]
    if str(ODOO_ENT_CONTAINER_PATH) in mounts:
        parts.append(str(ODOO_ENT_CONTAINER_PATH))
    for c in mounts:
        if c.startswith(str(EXTN_SRC_CONTAINER_PATH)):
            parts.append(c)
    return ",".join(parts)


def find_module_paths(
    modules: list[str],
    mounts: dict[str, Path],
) -> tuple[dict[str, str], list[str]]:
    """Returns ``{module_name: container_path}`` for each requested module.

    Exits with an error if any module cannot be located.
    """
    result: dict[str, str] = {}
    missing: list[str] = []
    for mod in modules:
        found = False
        for container, host in mounts.items():
            if container == str(ODOO_SRC_CONTAINER_PATH):
                candidates = (
                    (host / "odoo" / "addons" / mod, f"{container}/odoo/addons/{mod}"),
                    (host / "addons" / mod, f"{container}/addons/{mod}"),
                )
            else:
                candidates = ((host / mod, f"{container}/{mod}"),)
            for host_path, container_path in candidates:
                if host_path.is_dir():
                    result[mod] = container_path
                    found = True
                    break
            if found:
                break
        if not found:
            missing.append(mod)
    return result, missing
