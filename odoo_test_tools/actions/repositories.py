"""Repository management actions."""

from __future__ import annotations

import configparser
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from ..console import console, die
from ..defaults import ODOO_VERSION_FILE_NAME, WORK_DIR_NAME
from ..utils import run


def _repo_parts(url: str) -> tuple[str, str] | None:
    """Return the org and repository names encoded by a clone URL."""
    if "://" in url:
        parts = [part for part in urlsplit(url).path.split("/") if part]
    elif ":" in url and not url.startswith(("/", "./", "../")):
        parts = [part for part in url.rsplit(":", 1)[1].split("/") if part]
    else:
        return None
    if parts and parts[-1].endswith(".git"):
        parts[-1] = parts[-1][:-4]
    if len(parts) < 2 or any(part in ("", ".", "..") for part in parts[-2:]):
        return None
    return parts[-2], parts[-1]


def _repo_path(root: Path, path: Path) -> Path:
    candidate = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Repository path '{path}' must be inside root '{root}'.")
    if not candidate.is_dir() or not (candidate / ".git").exists():
        raise ValueError(f"'{candidate}' is not a Git repository.")
    return candidate


def _project_files(root: Path, name: str | None) -> tuple[Path, Path]:
    work_dir = root / WORK_DIR_NAME
    marker = work_dir / ODOO_VERSION_FILE_NAME
    if not marker.is_file():
        raise ValueError("Project is not initialized; run 'init' first.")
    try:
        version = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"Cannot read project version file '{marker}': {exc}") from exc
    project_name = name or version
    if project_name in ("", ".", "..") or Path(project_name).name != project_name:
        raise ValueError(f"Invalid project name '{project_name}'.")
    project = work_dir / project_name
    config = project / "odoo.cfg"
    compose = project / "docker-compose.yml"
    if not config.is_file() or not compose.is_file():
        raise ValueError(f"Project '{project_name}' is not initialized.")
    return config, compose


def _change_project_addon(
    root: Path,
    name: str | None,
    repo: Path,
    *,
    add: bool,
) -> None:
    config_path, compose_path = _project_files(root, name)
    repo_name = repo.name
    container_path = f"/odoo/external-src/{repo_name}"
    mount = f"{repo}:{container_path}"
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with config_path.open(encoding="utf-8") as source:
            parser.read_file(source)
        if not parser.has_section("options"):
            raise ValueError(f"Project config '{config_path}' has no [options] section.")
        current = [
            path.strip()
            for path in parser.get("options", "addons_path", fallback="").split(",")
            if path.strip()
        ]
        compose_text = compose_path.read_text(encoding="utf-8")
        mount_line = re.compile(
            rf"(?m)^[ \t]*-[ \t]+{re.escape(str(repo))}:{re.escape(container_path)}[ \t]*\n?"
        )
        if add:
            if container_path not in current:
                current.append(container_path)
            if not mount_line.search(compose_text):
                lines = compose_text.splitlines(keepends=True)
                odoo_index = next(
                    (i for i, line in enumerate(lines) if re.fullmatch(r"  odoo:\s*\n?", line)),
                    None,
                )
                if odoo_index is None:
                    raise ValueError(f"Cannot find the odoo service in '{compose_path}'.")
                volumes_index = next(
                    (
                        i for i in range(odoo_index + 1, len(lines))
                        if re.fullmatch(r"    volumes:\s*\n?", lines[i])
                    ),
                    None,
                )
                if volumes_index is None:
                    raise ValueError(f"Cannot find the odoo volumes in '{compose_path}'.")
                insert_at = volumes_index + 1
                while insert_at < len(lines) and (
                    lines[insert_at].startswith("      - ")
                    or lines[insert_at].startswith("          - ")
                ):
                    insert_at += 1
                lines.insert(insert_at, f"          - {mount}\n")
                compose_text = "".join(lines)
        else:
            current = [path for path in current if path != container_path]
            compose_text, removed = mount_line.subn("", compose_text)
            if not removed:
                raise ValueError(
                    f"Repository '{repo}' is not mounted in project '{name or 'default'}'."
                )

        parser.set("options", "addons_path", ",\n    ".join(current))
        with config_path.open("w", encoding="utf-8") as target:
            parser.write(target)
        compose_path.write_text(compose_text, encoding="utf-8")
    except (OSError, configparser.Error) as exc:
        raise ValueError(f"Cannot update project addon configuration: {exc}") from exc


def action_repo_add(
    *,
    root: Path,
    url: str,
    branch: str,
    name: str | None = None,
    init: bool = False,
    **kwargs,
) -> int:
    parts = _repo_parts(url)
    if parts is None:
        return die(f"Cannot determine <org>/<repo> from repository URL '{url}'.")
    if init:
        try:
            _project_files(root, name)
        except ValueError as exc:
            return die(str(exc))
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root):
        return die(f"Repository path '{target}' must be inside root '{root}'.")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        console.print(f"Repository '{target}' is not empty; skipping clone.")
        if init:
            if not target.is_dir():
                return die(f"Repository path '{target}' is not a directory.")
            try:
                _change_project_addon(root, name, target.resolve(), add=True)
            except ValueError as exc:
                return die(str(exc))
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    autoshare_clone = shutil.which("git-autoshare-clone")
    clone_command = [autoshare_clone] if autoshare_clone else ["git", "clone"]
    result = run(
        [*clone_command, "--branch", branch, "--", url, str(target)],
        cwd=root,
        check=False,
    )
    if result.returncode:
        return result.returncode
    if init:
        try:
            _change_project_addon(root, name, target.resolve(), add=True)
        except ValueError as exc:
            return die(str(exc))
    return 0


def action_repo_checkout(
    *, root: Path, path: Path, ref: str, **kwargs,
) -> int:
    try:
        repo = _repo_path(root, path)
    except ValueError as exc:
        return die(str(exc))
    if ref.startswith("-"):
        return die(f"Invalid repository ref '{ref}'.")
    return run(["git", "checkout", ref], cwd=repo, check=False).returncode


def action_repo_update(
    *,
    root: Path,
    path: Path | None = None,
    remote: str = "origin",
    branch: str | None = None,
    **kwargs,
) -> int:
    if not remote or remote.startswith("-"):
        return die(f"Invalid Git remote '{remote}'.")
    if branch is not None and (not branch or branch.startswith("-")):
        return die(f"Invalid Git branch '{branch}'.")
    if path is not None:
        try:
            repos = [_repo_path(root, path)]
        except ValueError as exc:
            return die(str(exc))
    else:
        repos = sorted(
            candidate
            for candidate in root.glob("*/*")
            if candidate.is_dir() and (candidate / ".git").exists()
        )

    returncode = 0
    for repo in repos:
        console.print(f"Updating repository '{repo}'...")
        current_branch_result = run(
            ["git", "branch", "--show-current"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if current_branch_result.returncode:
            detail = (current_branch_result.stderr or "").strip()
            message = f"Cannot determine the current branch of repository '{repo}'."
            if detail:
                message = f"{message} {detail}"
            return die(message, code=current_branch_result.returncode)
        current_branch = current_branch_result.stdout.strip()
        if not current_branch:
            return die(f"Cannot determine the current branch of repository '{repo}'.")
        if branch is not None and current_branch != branch:
            return die(
                f"Repository '{repo}' is on branch '{current_branch}', not '{branch}'."
            )
        result = run(["git", "pull", remote, current_branch], cwd=repo, check=False)
        if result.returncode and not returncode:
            returncode = result.returncode
    return returncode


def action_repo_rm(
    *,
    root: Path,
    path: Path,
    name: str | None = None,
    init: bool = False,
    **kwargs,
) -> int:
    try:
        repo = _repo_path(root, path)
        if init:
            _change_project_addon(root, name, repo, add=False)
    except ValueError as exc:
        return die(str(exc))
    try:
        shutil.rmtree(repo)
    except OSError as exc:
        return die(f"Cannot remove repository '{repo}': {exc}")
    return 0
