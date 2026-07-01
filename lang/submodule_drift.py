#!/usr/bin/env python3
"""Detect grammar submodule drift for lang/release.

A grammar submodule has "drifted" when its checked-out commit differs from the
one pinned in git; releasing then would record an ephemeral, uncommitted commit
in fyi/versions. Also catches the case where a submodule was never initialized
(empty working tree) -- that's just as unsafe to release from, but produces no
file for the usual checked-out-vs-pinned comparison to find. Importable (tests
in lang/test_submodule_drift.py) and runnable directly:
`./submodule_drift.py <fyi.list>` (paths relative to the cwd, as lang/release
passes them). Exits non-zero on drift.
"""
from __future__ import annotations

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

    ``checked_out``/``pinned`` are usually full commit SHAs, but either can
    instead be a sentinel describing why there's nothing to compare:
    ``checked_out="<not initialized>"`` (submodule never cloned, or
    ``deinit``-ed) or ``pinned="<not committed in superproject>"`` (submodule
    path added but not yet committed in the superproject).
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


def _submodule_statuses(repo_root: Path) -> dict[str, tuple[str, str]]:
    """Map each submodule's path (relative to ``repo_root``) to (status, sha).

    Parsed from ``git submodule status``, whose leading status char is ``-``
    for an uninitialized submodule (never cloned, or ``deinit``-ed), ``+`` for
    a checked-out commit that doesn't match the pin, or blank when clean. An
    uninitialized submodule has an empty working tree, so ``find_drift`` can't
    discover it by walking up from a file inside it -- there is no file inside
    it to walk up from. This is what makes that case detectable.
    """
    statuses: dict[str, tuple[str, str]] = {}
    for line in _git(["submodule", "status"], cwd=repo_root).splitlines():
        if not line:
            continue
        status, sha, path = line[0], line[1:41], line[42:].split(" ", 1)[0]
        statuses[path] = (status, sha)
    return statuses


def find_drift(fyi_list: Path, root: Path) -> list[Drift]:
    """Return the drifted submodules referenced by ``fyi_list``.

    Paths in ``fyi_list`` (and ``fyi_list`` itself) are resolved relative to
    ``root`` -- the directory lang/release runs from. Entries that are not
    inside a submodule are ignored, and each submodule is reported at most
    once. An entry inside a submodule that was never initialized is reported
    even though the entry's file doesn't exist on disk (see
    ``_submodule_statuses``). Returns an empty list when there is no drift.
    Every language ships an fyi.list, so a missing one is an error, not
    "nothing to check".

    Raises ``FileNotFoundError`` if ``fyi_list`` doesn't exist, or
    ``subprocess.CalledProcessError`` if ``root`` isn't inside a git
    repository or a git command otherwise fails unexpectedly. The CLI
    (``main``) turns both into a clean, actionable error message.
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
    submodules: dict[str, tuple[str, str]],
    seen: set[str],
    drifts: list[Drift],
) -> None:
    """Record a Drift if ``file_path`` sits inside an uninitialized submodule.

    ``file_path`` doesn't exist on disk, so it's either not a submodule path
    at all, or it's inside a submodule with an empty working tree -- the two
    look identical from a plain existence check, which is why this needs
    ``submodules`` (from ``git submodule status``) to tell them apart.
    """
    try:
        rel = file_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return  # outside the superproject entirely (e.g. a bad fyi.list path)
    for sm_path, (status, sha) in submodules.items():
        if status == "-" and (rel == sm_path or rel.startswith(sm_path + "/")):
            if sm_path not in seen:
                seen.add(sm_path)
                drifts.append(
                    Drift(path=sm_path, checked_out="<not initialized>", pinned=sha)
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
    """CLI entry point: ``argv`` is ``sys.argv`` (program name + one path).

    Exit codes: 2 for a usage error or a missing/unreadable fyi.list or repo,
    1 if drift was detected, 0 if clean.
    """
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
