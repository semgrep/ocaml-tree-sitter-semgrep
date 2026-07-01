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
SM_PATH_2 = "semgrep-grammars/src/tree-sitter-bar"


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


def make_grammar_repo(path: Path) -> None:
    """A standalone git repo with one commit, suitable for use as a submodule."""
    path.mkdir()
    git("init", "-qb", "main", cwd=path)
    (path / "grammar.js").write_text("// grammar\n")
    git("add", "-A", cwd=path)
    git("commit", "-qm", "grammar", cwd=path)


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *args], cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A superproject pinning tree-sitter-foo, plus a non-submodule fyi entry."""
    make_grammar_repo(tmp_path / "grammar-src")

    super_ = tmp_path / "super"
    super_.mkdir()
    git("init", "-qb", "main", cwd=super_)
    git(
        "submodule", "add", "-q",
        (tmp_path / "grammar-src").as_uri(), SM_PATH,
        cwd=super_,
    )
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


def test_dedups_multiple_entries_in_same_submodule(repo: Path) -> None:
    # A second fyi.list entry inside the already-pinned submodule must not
    # produce a second Drift for the same path.
    (repo / "foo" / "fyi.list").write_text(
        f"{SM_PATH}/grammar.js\n{SM_PATH}/grammar.js\nwrapper/grammar.js\n"
    )
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)
    drifts = find_drift(Path("foo/fyi.list"), root=repo)
    assert [d.path for d in drifts] == [SM_PATH]


def test_mixed_drift_across_multiple_submodules(repo: Path) -> None:
    # A second, clean submodule alongside the drifted one: only the drifted
    # one should be reported, proving iteration doesn't stop after the first
    # submodule or conflate the two.
    make_grammar_repo(repo.parent / "grammar-src-2")
    git(
        "submodule", "add", "-q",
        (repo.parent / "grammar-src-2").as_uri(), SM_PATH_2,
        cwd=repo,
    )
    git("commit", "-qm", "pin tree-sitter-bar", cwd=repo)
    (repo / "foo" / "fyi.list").write_text(
        f"{SM_PATH}/grammar.js\n{SM_PATH_2}/grammar.js\n"
    )
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)

    drifts = find_drift(Path("foo/fyi.list"), root=repo)
    assert [d.path for d in drifts] == [SM_PATH]


def test_uninitialized_submodule_is_reported(repo: Path) -> None:
    # deinit empties the submodule's working tree without unpinning it, so
    # there's no file left for the usual walk-up-from-a-file check to find.
    git("submodule", "deinit", "-f", SM_PATH, cwd=repo)
    drifts = find_drift(Path("foo/fyi.list"), root=repo)
    assert [d.path for d in drifts] == [SM_PATH]
    assert drifts[0].checked_out == "<not initialized>"
    assert drifts[0].pinned  # the pinned sha, still known from the index


def test_uncommitted_submodule_pin_reports_readable_message(repo: Path) -> None:
    # A submodule staged with 'git submodule add' but not yet committed: HEAD
    # doesn't know about the path yet, so there's no pinned commit to compare.
    make_grammar_repo(repo.parent / "grammar-src-2")
    git(
        "submodule", "add", "-q",
        (repo.parent / "grammar-src-2").as_uri(), SM_PATH_2,
        cwd=repo,
    )
    (repo / "foo" / "fyi.list").write_text(f"{SM_PATH_2}/grammar.js\n")

    drifts = find_drift(Path("foo/fyi.list"), root=repo)
    assert [d.path for d in drifts] == [SM_PATH_2]
    assert drifts[0].pinned == "<not committed in superproject>"
    assert "not committed in superproject" in str(drifts[0])


def test_cli_exit_codes(repo: Path) -> None:
    clean = run_cli("foo/fyi.list", cwd=repo)
    assert clean.returncode == 0, clean.stderr

    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)
    drifted = run_cli("foo/fyi.list", cwd=repo)
    assert drifted.returncode == 1
    assert "drift detected" in drifted.stderr
    assert "tree-sitter-foo" in drifted.stderr


def test_cli_usage_error_on_wrong_argc(repo: Path) -> None:
    for args in ((), ("foo/fyi.list", "extra")):
        result = run_cli(*args, cwd=repo)
        assert result.returncode == 2
        assert "Usage:" in result.stderr


def test_cli_missing_fyi_list_exit_code(repo: Path) -> None:
    result = run_cli("foo/does-not-exist.list", cwd=repo)
    assert result.returncode == 2
    assert "Error: missing fyi.list" in result.stderr


def test_cli_reports_clean_error_on_unexpected_git_failure(repo: Path) -> None:
    # A submodule-shaped directory whose repo has zero commits: HEAD is
    # unborn, so 'git rev-parse HEAD' fails for a reason find_drift doesn't
    # special-case. The CLI should still print a clean 'Error:' line instead
    # of leaking a raw traceback -- this is what lang/release's caller sees.
    broken_sm = repo / "semgrep-grammars" / "src" / "tree-sitter-broken"
    broken_sm.mkdir(parents=True)
    git("init", "-qb", "main", cwd=broken_sm)
    (repo / "foo" / "fyi.list").write_text(
        "semgrep-grammars/src/tree-sitter-broken/grammar.js\n"
    )
    (broken_sm / "grammar.js").write_text("// grammar\n")

    result = run_cli("foo/fyi.list", cwd=repo)
    assert result.returncode == 2
    assert "Error:" in result.stderr
