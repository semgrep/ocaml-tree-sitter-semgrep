"""Tests for lang/check_submodule_pinned. Builds a throwaway superproject
with a grammar submodule under pytest's ``tmp_path`` (cleaned up
automatically) to exercise drift detection end to end."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parent / "check_submodule_pinned"
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


def run_check(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
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
    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert "all pinned" in result.stdout


def test_detects_drift(repo: Path) -> None:
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)
    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "modified" in result.stderr.lower()
    assert "tree-sitter-foo" in result.stderr


def test_missing_fyi_list(repo: Path) -> None:
    result = run_check("foo/does-not-exist.list", cwd=repo)
    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_dedups_multiple_entries_in_same_submodule(repo: Path) -> None:
    (repo / "foo" / "fyi.list").write_text(
        f"{SM_PATH}/grammar.js\n{SM_PATH}/grammar.js\nwrapper/grammar.js\n"
    )
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)
    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert result.stderr.count("tree-sitter-foo") == 1


def test_mixed_drift_across_multiple_submodules(repo: Path) -> None:
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

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "tree-sitter-foo" in result.stderr
    assert "tree-sitter-bar" not in result.stderr


def test_uninitialized_submodule_is_reported(repo: Path) -> None:
    git("submodule", "deinit", "-f", SM_PATH, cwd=repo)
    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "not initialized" in result.stderr.lower()
    assert "tree-sitter-foo" in result.stderr


def test_uncommitted_new_submodule_is_reported(repo: Path) -> None:
    make_grammar_repo(repo.parent / "grammar-src-2")
    git(
        "submodule", "add", "-q",
        (repo.parent / "grammar-src-2").as_uri(), SM_PATH_2,
        cwd=repo,
    )
    (repo / "foo" / "fyi.list").write_text(f"{SM_PATH_2}/grammar.js\n")

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "tree-sitter-bar" in result.stderr


def test_submodules_handles_paths_with_spaces(tmp_path: Path) -> None:
    make_grammar_repo(tmp_path / "grammar-src")
    super_ = tmp_path / "super"
    super_.mkdir()
    git("init", "-qb", "main", cwd=super_)
    sm_path = "semgrep-grammars/src/tree sitter foo"
    git(
        "submodule", "add", "-q",
        (tmp_path / "grammar-src").as_uri(), sm_path,
        cwd=super_,
    )
    git("commit", "-qm", "pin", cwd=super_)
    git("submodule", "deinit", "-f", sm_path, cwd=super_)
    (super_ / "fyi.list").write_text(f"{sm_path}/grammar.js\n")

    result = run_check("fyi.list", cwd=super_)
    assert result.returncode == 1
    assert "tree sitter foo" in result.stderr


def test_unregistered_directory_is_ignored(repo: Path) -> None:
    stray = repo / "semgrep-grammars" / "src" / "tree-sitter-stray"
    stray.mkdir(parents=True)
    git("init", "-qb", "main", cwd=stray)
    (stray / "grammar.js").write_text("// grammar\n")
    (repo / "foo" / "fyi.list").write_text(
        "semgrep-grammars/src/tree-sitter-stray/grammar.js\n"
    )

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 0, result.stderr


def test_detects_drift_when_tracked_file_deleted_from_submodule(repo: Path) -> None:
    (repo / SM_PATH / "grammar.js").unlink()

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "tree-sitter-foo" in result.stderr


def test_help(repo: Path) -> None:
    result = run_check("--help", cwd=repo)
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_not_a_git_repository(tmp_path: Path) -> None:
    (tmp_path / "fyi.list").write_text("some/file.js\n")
    result = run_check("fyi.list", cwd=tmp_path)
    assert result.returncode != 0
