"""Merge several requirements.txt files into one, combining constraints.

Rules:
  * same package listed more than once -> constraints are combined
    (factur-x  + factur-x<=3.1        => factur-x<=3.1)
    (factur-x>=2 + factur-x<=3.1      => factur-x>=2,<=3.1)
  * only the tightest lower/upper bound is kept
  * contradictory constraints -> error, exit code 1
    (factur-x>3.1 + factur-x<3.0      => error)

Requires: pip install packaging
"""
from collections import OrderedDict
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from .utils import console


class Group:
    """All the occurrences of one requirement (same name, extras, marker)."""

    def __init__(self, req: Requirement):
        self.name: str = req.name
        self.extras: list[str] = sorted(req.extras)
        self.marker: str = str(req.marker) if req.marker else ""
        self.specs: list[tuple[str, str]] = []  # (operator, version)
        self.sources: list[str] = []  # "file:line"

    def add(self, req: Requirement, source: str):
        self.sources.append(source)
        for spec in req.specifier:
            item: tuple[str, str] = (spec.operator, spec.version)
            if item not in self.specs:
                self.specs.append(item)

    def merge(self):
        """Return the merged requirement string, or raise ValueError."""
        lowers, uppers, eqs, others = [], [], [], []
        for op, ver in self.specs:
            if op in (">", ">=", "<", "<=") or (op == "==" and "*" not in ver):
                try:
                    v = Version(ver)
                except InvalidVersion:
                    others.append((op, ver))
                    continue
                if op in (">", ">="):
                    lowers.append((v, op == ">="))
                elif op in ("<", "<="):
                    uppers.append((v, op == "<="))
                else:
                    eqs.append(v)
            else:  # !=, ~=, ===, ==1.*  -> kept as is, left to pip
                others.append((op, ver))

        # tightest bounds: highest lower, lowest upper; on a tie, exclusive wins
        lo = max(lowers, key=lambda b: (b[0], not b[1]), default=None)
        hi = min(uppers, key=lambda b: (b[0], b[1]), default=None)

        if lo and hi:
            if lo[0] > hi[0] or (lo[0] == hi[0] and not (lo[1] and hi[1])):
                raise ValueError(
                    f"Empty range: {self._fmt_bound(lo, True)}"
                    f" vs {self._fmt_bound(hi, False)}"
                )
        if len({str(v) for v in eqs}) > 1 or len(set(eqs)) > 1:
            raise ValueError(
                f"Different pinned versions: {', '.join(sorted({str(v) for v in eqs}))}"
            )
        if eqs:
            v = eqs[0]
            if lo and not (v > lo[0] or (lo[1] and v == lo[0])):
                raise ValueError(f"=={v} violates {self._fmt_bound(lo, True)}")
            if hi and not (v < hi[0] or (hi[1] and v == hi[0])):
                raise ValueError(f"=={v} violates {self._fmt_bound(hi, False)}")
            lo = hi = None  # the pin makes the bounds redundant

        parts = []
        if lo:
            parts.append(self._fmt_bound(lo, True))
        if hi:
            parts.append(self._fmt_bound(hi, False))
        if eqs:
            parts.append(f"=={eqs[0]}")
        parts += sorted(f"{op}{ver}" for op, ver in others)

        text = self.name
        if self.extras:
            text += "[" + ",".join(self.extras) + "]"
        text += ",".join(parts)
        if self.marker:
            text += f" ; {self.marker}"
        return text

    @staticmethod
    def _fmt_bound(bound, is_lower):
        version, inclusive = bound
        op = (">" if is_lower else "<") + ("=" if inclusive else "")
        return f"{op}{version}"


def parse_files(paths: list[str | Path]):
    groups = OrderedDict()
    passthrough = OrderedDict()  # lines we can't merge (urls, -e, options...)
    for path in paths:
        for lineno, raw in enumerate(Path(path).read_text().splitlines(), 1):
            line = raw.split(" #")[0].strip()
            if not line or line.startswith("#"):
                continue
            source = f"{path}:{lineno}"
            if line.startswith("-"):
                passthrough.setdefault(line, source)
                continue
            try:
                req = Requirement(line)
            except InvalidRequirement:
                console.print(
                    f"Cannot parse requirement at {source}: {line!r}; keeping it unchanged",
                    style="yellow",
                )
                passthrough.setdefault(line, source)
                continue
            if req.url:
                passthrough.setdefault(line, source)
                continue
            key = (
                canonicalize_name(req.name),
                tuple(sorted(req.extras)),
                str(req.marker) if req.marker else "",
            )
            groups.setdefault(key, Group(req)).add(req, source)
    return groups, passthrough


def merge_requirements(paths: list[str | Path]) -> tuple[list[str], list[str]]:
    groups, passthrough = parse_files(paths)
    lines, errors = [], []
    for group in groups.values():
        try:
            lines.append(group.merge())
        except ValueError as exc:
            errors.append(
                f"Conflict for '{group.name}': {exc}\n"
                f"    {'\n    '.join(group.sources)}"
            )
    return sorted(lines, key=str.lower) + list(passthrough), errors


def generate_requirements_file(path: Path, requirements: list[str]) -> None:
    """Write a minimal requirements.txt that installs the official Odoo image."""
    path.write_text("\n".join(requirements), encoding="utf-8")
