#!/usr/bin/env python3
"""Detect grammar submodule drift (checked-out commit != pinned commit) for
lang/release. Importable, or runnable directly: `./submodule_drift.py
<fyi.list>`. Exits non-zero on drift.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def _short(commit: str) -> str:
    """Shorten a full commit SHA for display; pass sentinel strings through."""
    return commit[:12] if len(commit) == 40 else commit


@dataclass(frozen=True)
class Drift:
    """A submodule whose checked-out commit differs from its pinned commit.

    ``checked_out``/``pinned`` hold a sentinel instead of a SHA when there's
    nothing to compare (submodule not initialized, or pin not yet committed).
    """

    path: str  # submodule path relative to the superproject root
    checked_out: str  # commit currently in the submodule working tree
    pinned: str  # commit recorded (pinned) in the superproject

    def __str__(self) -> str:
        return (
            f"  {self.path}: checked out {_short(self.checked_out)}, "
            f"pinned {_short(self.pinned)}"
        )


def _git(args: list[str], cwd: Path) -> str:
    """Run git in ``cwd``; raises ``CalledProcessError`` on a non-zero exit."""
    return _run_git(args, cwd).stdout.strip()


def _git_lines(args: list[str], cwd: Path) -> list[str]:
    """Like ``_git``, but preserves each line's leading whitespace -- some git
    output (e.g. submodule status's flag column) encodes meaning there, which
    a plain ``.strip()`` of the whole output would eat for a one-line result.
    """
    return _run_git(args, cwd).stdout.splitlines()


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _fyi_entries(fyi_list: Path) -> list[str]:
    """Non-comment, non-blank paths listed in an fyi.list file."""
    return [
        stripped
        for line in fyi_list.read_text().splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]


@dataclass(frozen=True)
class SubmoduleStatus:
    """A submodule's state per ``git submodule status``."""

    initialized: bool
    sha: str  # commit recorded in the superproject's index


_STATUS_LINE = re.compile(
    r"^(?P<flag>.)(?P<sha>[0-9a-f]{40}) (?P<path>.+?)(?: \([^()]*\))?$"
)


def _submodule_statuses(repo_root: Path) -> dict[str, SubmoduleStatus]:
    """Map each submodule path (relative to ``repo_root``) to its status."""
    lines = _git_lines(["submodule", "status"], cwd=repo_root)
    matches = filter(None, map(_STATUS_LINE.match, lines))
    return {
        m["path"]: SubmoduleStatus(initialized=m["flag"] != "-", sha=m["sha"])
        for m in matches
    }


def find_drift(fyi_list: Path, root: Path) -> list[Drift]:
    """Return the drifted submodules referenced by ``fyi_list``, resolved
    relative to ``root``. Non-submodule entries are ignored; each submodule
    is reported at most once.

    Raises ``FileNotFoundError`` if ``fyi_list`` doesn't exist, or
    ``subprocess.CalledProcessError`` on an unexpected git failure.
    """
    fyi_path = fyi_list if fyi_list.is_absolute() else root / fyi_list
    if not fyi_path.exists():
        raise FileNotFoundError(f"missing fyi.list: {fyi_path}")

    repo_root = Path(_git(["rev-parse", "--show-toplevel"], cwd=root)).resolve()
    submodules = _submodule_statuses(repo_root)
    drifts: list[Drift] = []
    seen: set[str] = set()

    for entry in _fyi_entries(fyi_path):
        file_path = root / entry
        if not file_path.exists():
            _report_if_uninitialized(file_path, repo_root, submodules, seen, drifts)
            continue

        containing_dir = file_path.parent
        try:
            sm_root = Path(
                _git(["rev-parse", "--show-toplevel"], cwd=containing_dir)
            )
        except subprocess.CalledProcessError:
            continue
        if sm_root == repo_root:
            continue  # not in a submodule
        rel = sm_root.relative_to(repo_root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)

        checked_out = _git(["rev-parse", "HEAD"], cwd=sm_root)
        ls_tree = _git(["ls-tree", "HEAD", rel], cwd=repo_root)
        # ls-tree line format: "<mode> <type> <sha>\t<path>"; [2] is the sha.
        pinned = ls_tree.split()[2] if ls_tree else "<not committed in superproject>"
        if checked_out != pinned:
            drifts.append(Drift(path=rel, checked_out=checked_out, pinned=pinned))

    return drifts


def _report_if_uninitialized(
    file_path: Path,
    repo_root: Path,
    submodules: dict[str, SubmoduleStatus],
    seen: set[str],
    drifts: list[Drift],
) -> None:
    """Record a Drift if ``file_path`` (which doesn't exist on disk) sits
    inside an uninitialized submodule rather than just not being one."""
    try:
        rel = file_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return  # outside the superproject entirely (e.g. a bad fyi.list path)
    for sm_path, status in submodules.items():
        if status.initialized:
            continue
        if rel == sm_path or rel.startswith(sm_path + "/"):
            if sm_path not in seen:
                seen.add(sm_path)
                drifts.append(
                    Drift(path=sm_path, checked_out="<not initialized>", pinned=status.sha)
                )
            return


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
    """CLI entry point. Exit codes: 2 usage/setup error, 1 drift found, 0 clean."""
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} <fyi.list>", file=sys.stderr)
        return 2
    try:
        drifts = find_drift(Path(argv[1]), root=Path.cwd())
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"Error: {exc.stderr.strip() or exc}", file=sys.stderr)
        return 2
    if drifts:
        print("Error: " + format_error(drifts), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
