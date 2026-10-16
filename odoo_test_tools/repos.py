"""Multirepo scanning and addon path utilities."""

from __future__ import annotations

from pathlib import Path

from .defaults import odoo_ent_container_path, extn_src_container_path, odoo_src_container_path
from .utils import console, die


def collect_repos(
    root: Path,
    work_dir: Path,
    version: str,
    *,
    include_enterprise: bool,
    exclude_addons_paths: list[Path] | None = None,
    restrict_addons_paths: list[Path] | None = None,
) -> dict[str, Path]:
    """
    Scan ``<root>/<org>/<repo>/<version>/`` and return
    ``{container_path: host_path}`` for every matching directory.

    Layout:
        odoo/odoo/<version>        → /odoo/src
        odoo/enterprise/<version>  → /odoo/enterprise-src
        <org>/<repo>/<version>     → /odoo/external-src/<repo>
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
        if {".odoo-test-tools"}.intersection(repo_dir.parts):
            continue
        repo_name = f"{repo_dir.parent.name}/{repo_dir.name}"
        is_community = repo_name == "odoo/odoo"
        if not is_community and (
            repo_name in excluded or (restricted and repo_name not in restricted)
        ):
            continue
        org = repo_dir.parent.name
        repo = repo_dir.name
        version_path = repo_dir / version
        if not version_path.is_dir() or version_path.is_relative_to(work_dir):
            continue
        if org == "odoo" and repo == "odoo":
            container = str(odoo_src_container_path)
        elif org == "odoo" and repo == "enterprise":
            if not include_enterprise:
                console.print(f"  [yellow]↷ skipping odoo/enterprise/{version} (--no-enterprise)[/yellow]")
                continue
            container = str(odoo_ent_container_path)
        else:
            container = f"{extn_src_container_path}/{repo}"
        mounts[container] = version_path
        console.print(f"  [green]✔[/green] {org}/{repo}/{version} → {container}")
    return mounts


def build_addons_path(mounts: dict[str, Path]) -> str:
    """Build the comma-separated Odoo ``--addons-path`` value from collected mounts

    Order: CE built-ins → CE addons → Enterprise → external repos.
    """
    parts: list[str] = []
    if str(odoo_src_container_path) in mounts:
        parts += [
            f"{odoo_src_container_path}/odoo/addons",
            f"{odoo_src_container_path}/addons",
        ]
    if str(odoo_ent_container_path) in mounts:
        parts.append(str(odoo_ent_container_path))
    for c in mounts:
        if c.startswith(str(extn_src_container_path)):
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
            if container == str(odoo_src_container_path):
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
