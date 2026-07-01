"""Tests for lang/submodule_drift.py (module + CLI entry point).

Builds a throwaway superproject with a grammar submodule, then checks that
drift detection is empty when the submodule matches its pinned commit and
non-empty when the working tree has drifted from the pin.

Everything is created under pytest's ``tmp_path`` fixture, which lives inside
the session temp root managed by ``tmp_path_factory``. pytest removes those
directories automatically (retaining only the last few runs), so an aborted or
failed test never leaks -- there is no manual teardown to get wrong.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from submodule_drift import find_drift  # noqa: E402

CLI = Path(__file__).resolve().parent / "submodule_drift.py"
SM_PATH = "semgrep-grammars/src/tree-sitter-foo"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(
        [
            "git",
            "-c", "user.email=test@example.com",
            "-c", "user.name=test",
            "-c", "commit.gpgsign=false",
            "-c", "protocol.file.allow=always",
            *args,
        ],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A superproject pinning tree-sitter-foo, plus a non-submodule fyi entry."""
    sub = tmp_path / "grammar-src"
    sub.mkdir()
    git("init", "-qb", "main", cwd=sub)
    (sub / "grammar.js").write_text("// grammar\n")
    git("add", "-A", cwd=sub)
    git("commit", "-qm", "grammar", cwd=sub)

    super_ = tmp_path / "super"
    super_.mkdir()
    git("init", "-qb", "main", cwd=super_)
    git("submodule", "add", "-q", sub.as_uri(), SM_PATH, cwd=super_)
    # A file NOT in a submodule, to prove those entries are ignored.
    (super_ / "wrapper").mkdir()
    (super_ / "wrapper" / "grammar.js").write_text("// wrapper\n")
    git("add", "-A", cwd=super_)
    git("commit", "-qm", "pin tree-sitter-foo", cwd=super_)

    lang_dir = super_ / "foo"
    lang_dir.mkdir()
    (lang_dir / "fyi.list").write_text(
        f"# grammar sources\n{SM_PATH}/grammar.js\nwrapper/grammar.js\n"
    )
    return super_


def test_no_drift_when_submodule_matches_pin(repo: Path) -> None:
    assert find_drift(Path("foo/fyi.list"), root=repo) == []


def test_detects_drift(repo: Path) -> None:
    # Move the submodule off its pinned commit without committing a new pin.
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)
    drifts = find_drift(Path("foo/fyi.list"), root=repo)
    assert [d.path for d in drifts] == [SM_PATH]
    assert drifts[0].checked_out != drifts[0].pinned


def test_missing_fyi_list_raises(repo: Path) -> None:
    # Every language ships an fyi.list, so a missing one is an error.
    with pytest.raises(FileNotFoundError):
        find_drift(Path("foo/does-not-exist.list"), root=repo)


def test_cli_exit_codes(repo: Path) -> None:
    clean = subprocess.run(
        [str(CLI), "foo/fyi.list"], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert clean.returncode == 0, clean.stderr

    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)
    drifted = subprocess.run(
        [str(CLI), "foo/fyi.list"], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert drifted.returncode == 1
    assert "drift detected" in drifted.stderr
    assert "tree-sitter-foo" in drifted.stderr
