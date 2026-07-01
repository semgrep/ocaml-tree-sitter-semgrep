#!/usr/bin/env python3
"""Detect grammar submodule drift for lang/release.

A grammar submodule has "drifted" when its checked-out commit differs from the
one pinned in git; releasing then would record an ephemeral, uncommitted commit
in fyi/versions. Importable (tests in lang/test_submodule_drift.py) and runnable
directly: `./submodule_drift.py <fyi.list>` (paths relative to the cwd, as
lang/release passes them). Exits non-zero on drift.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Drift:
    """A submodule whose checked-out commit differs from its pinned commit."""

    path: str  # submodule path relative to the superproject root
    checked_out: str  # commit currently in the submodule working tree
    pinned: str  # commit recorded (pinned) in the superproject

    def __str__(self) -> str:
        return (
            f"  {self.path}: checked out {self.checked_out[:12]}, "
            f"pinned {self.pinned[:12]}"
        )


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _fyi_entries(fyi_list: Path) -> list[str]:
    """Non-comment, non-blank paths listed in an fyi.list file."""
    return [
        stripped
        for line in fyi_list.read_text().splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]


def find_drift(fyi_list: Path, root: Path) -> list[Drift]:
    """Return the drifted submodules referenced by ``fyi_list``.

    Paths in ``fyi_list`` (and ``fyi_list`` itself) are resolved relative to
    ``root`` -- the directory lang/release runs from. Entries that are not
    inside a submodule are ignored, and each submodule is reported at most once.
    Returns an empty list when there is no drift. Every language ships an
    fyi.list, so a missing one is an error, not "nothing to check".
    """
    fyi_path = fyi_list if fyi_list.is_absolute() else root / fyi_list
    if not fyi_path.exists():
        raise FileNotFoundError(f"missing fyi.list: {fyi_path}")

    repo_root = Path(_git(["rev-parse", "--show-toplevel"], cwd=root))
    drifts: list[Drift] = []
    seen: set[Path] = set()

    for entry in _fyi_entries(fyi_path):
        file_path = root / entry
        if not file_path.exists():
            continue
        containing_dir = file_path.parent
        try:
            sm_root = Path(
                _git(["rev-parse", "--show-toplevel"], cwd=containing_dir)
            )
        except subprocess.CalledProcessError:
            continue
        if sm_root == repo_root or sm_root in seen:
            continue  # not in a submodule, or already reported
        seen.add(sm_root)

        checked_out = _git(["rev-parse", "HEAD"], cwd=sm_root)
        rel = sm_root.relative_to(repo_root).as_posix()
        ls_tree = _git(["ls-tree", "HEAD", rel], cwd=repo_root)
        pinned = ls_tree.split()[2] if ls_tree else ""
        if checked_out != pinned:
            drifts.append(Drift(path=rel, checked_out=checked_out, pinned=pinned))

    return drifts


def format_error(drifts: list[Drift]) -> str:
    """Human-readable, actionable message describing the drift."""
    lines = [
        "grammar submodule drift detected (checked-out commit != pinned commit):",
        *(str(d) for d in drifts),
        "",
        "Releasing would generate the parser from, and record in fyi/versions,",
        "an uncommitted commit. Decide what you intended, then re-run:",
        "  - reset to the pinned commit:  "
        "git submodule update --init --checkout <path>",
        "  - or commit the new pin:       git add <path> && git commit",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} <fyi.list>", file=sys.stderr)
        return 2
    try:
        drifts = find_drift(Path(argv[1]), root=Path.cwd())
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if drifts:
        print("Error: " + format_error(drifts), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
