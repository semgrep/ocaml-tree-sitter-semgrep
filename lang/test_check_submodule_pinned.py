"""Tests for lang/check_submodule_pinned. Builds a throwaway superproject
with a grammar submodule under pytest's ``tmp_path`` (cleaned up
automatically) to exercise drift detection end to end."""
from __future__ import annotations

import os
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
    # fyi.list entries are relative to `cwd` here (our throwaway repo),
    # not to the real check_submodule_pinned's own directory, so override
    # the base directory the script would otherwise default to.
    env = {**os.environ, "CHECK_SUBMODULE_PINNED_DIR": str(cwd)}
    return subprocess.run(
        [str(CLI), *args], cwd=cwd, text=True, env=env,
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


def test_fyi_entry_is_the_submodule_path_itself(repo: Path) -> None:
    # fyi.list can name the submodule directory directly, not just a file
    # inside it -- the 'entry == sm' branch of is_referenced, as opposed to
    # the 'entry starts with sm/' branch every other test exercises.
    (repo / "foo" / "fyi.list").write_text(f"{SM_PATH}\n")
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "tree-sitter-foo" in result.stderr


def test_prefix_collision_without_slash_boundary_is_not_a_match(repo: Path) -> None:
    # 'tree-sitter-foobar/grammar.js' shares a string prefix with the
    # submodule path 'tree-sitter-foo' but isn't inside it (no '/' right
    # after 'foo'). is_referenced must require that boundary, not just a
    # prefix match, or an unrelated drifted submodule would be reported.
    (repo / "foo" / "fyi.list").write_text(
        "semgrep-grammars/src/tree-sitter-foobar/grammar.js\n"
    )
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 0, result.stderr


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


def test_uninitialized_check_short_circuits_before_modified_check(repo: Path) -> None:
    # tree-sitter-foo is uninitialized AND (also-referenced) tree-sitter-bar
    # is modified: only the uninitialized error should surface, proving the
    # two checks run as separate, fail-fast phases rather than one combined
    # pass that could report both at once.
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
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH_2)
    git("submodule", "deinit", "-f", SM_PATH, cwd=repo)

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 1
    assert "not initialized" in result.stderr.lower()
    assert "tree-sitter-foo" in result.stderr
    assert "modified" not in result.stderr.lower()
    assert "tree-sitter-bar" not in result.stderr


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


def test_repo_with_no_submodules_at_all(tmp_path: Path) -> None:
    # A repo with zero '160000' (gitlink) entries at all -- guards the
    # mode-filtering loop against ever mistaking "found nothing to check"
    # for an error.
    super_ = tmp_path / "super"
    super_.mkdir()
    git("init", "-qb", "main", cwd=super_)
    (super_ / "plain.js").write_text("// plain\n")
    git("add", "-A", cwd=super_)
    git("commit", "-qm", "init", cwd=super_)
    (super_ / "fyi.list").write_text("plain.js\n")

    result = run_check("fyi.list", cwd=super_)
    assert result.returncode == 0, result.stderr
    assert "all pinned" in result.stdout


def test_empty_fyi_list_has_nothing_to_check(repo: Path) -> None:
    # Comments and a blank line only: entries ends up empty, so no
    # submodule is ever referenced -- even though tree-sitter-foo is
    # genuinely drifted, there's nothing in this fyi.list to catch it.
    (repo / "foo" / "fyi.list").write_text("# nothing referenced here\n\n")
    git("commit", "-q", "--allow-empty", "-m", "drift", cwd=repo / SM_PATH)

    result = run_check("foo/fyi.list", cwd=repo)
    assert result.returncode == 0, result.stderr


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


def test_help_short_flag(repo: Path) -> None:
    result = run_check("-h", cwd=repo)
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_wrong_argument_count_prints_usage(repo: Path) -> None:
    for args in ((), ("foo/fyi.list", "extra")):
        result = run_check(*args, cwd=repo)
        assert result.returncode == 0
        assert "Usage:" in result.stdout


def test_not_a_git_repository(tmp_path: Path) -> None:
    (tmp_path / "fyi.list").write_text("some/file.js\n")
    result = run_check("fyi.list", cwd=tmp_path)
    assert result.returncode != 0
    # A bare "some error happened" isn't enough: git's own diagnostic must
    # actually reach the user, not be silently swallowed.
    assert "not a git repository" in result.stderr.lower()
