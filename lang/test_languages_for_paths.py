"""Unit tests for lang/scripts/languages-for-paths."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

LANG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LANG_DIR))

from grammar_dependencies import unpopulated_grammar_dirs  # noqa: E402

SCRIPT = LANG_DIR / "scripts" / "languages-for-paths"
SRC = "lang/semgrep-grammars/src"

# The reference graph is read out of the upstream grammars, so narrowing only
# works when the submodules are checked out. Without them the script must fall
# back to the full matrix -- asserted by test_uninitialised_submodules_* below.
SUBMODULES_PRESENT = not unpopulated_grammar_dirs(LANG_DIR / "semgrep-grammars" / "src")
needs_submodules = pytest.mark.skipif(
    not SUBMODULES_PRESENT, reason="grammar submodules not initialised"
)


def run(*paths: str) -> tuple[list[str], str]:
    proc = subprocess.run(
        [SCRIPT], input="\n".join(paths), capture_output=True, text=True, check=True
    )
    return proc.stdout.split(), proc.stderr


def all_languages() -> list[str]:
    return subprocess.run(
        [LANG_DIR / "scripts" / "list-languages"], capture_output=True, text=True, check=True
    ).stdout.split()


@needs_submodules
def test_language_own_dir_narrows_to_that_language():
    assert run(f"{SRC}/semgrep-lua/grammar.js")[0] == ["lua"]


@needs_submodules
def test_follows_references_between_grammars():
    """tree-sitter-c is read by cpp (live require), not solidity (comment only)."""
    assert set(run(f"{SRC}/tree-sitter-c/src/parser.c")[0]) == {"c", "cpp"}
    assert run(f"{SRC}/tree-sitter-c-sharp/grammar.js")[0] == ["c-sharp"]
    assert run(f"{SRC}/tree-sitter-c-sharp-pro/grammar.js")[0] == ["c-sharp-pro"]
    assert run(f"{SRC}/tree-sitter-powershell/grammar.js")[0] == ["powershell"]
    assert run(f"{SRC}/tree-sitter-go-mod/grammar.js")[0] == ["gomod"]


@needs_submodules
def test_javascript_and_typescript_bidirectional():
    """JS upstream pulls typescript; TS upstream does not pull javascript."""
    assert set(run(f"{SRC}/tree-sitter-javascript/grammar.js")[0]) == {
        "javascript",
        "typescript",
    }
    assert run(f"{SRC}/tree-sitter-typescript/typescript/grammar.js")[0] == ["typescript"]


@needs_submodules
def test_unresolved_grammar_dir_selects_everything():
    """Fail closed: a tree-sitter dir with no language must not skip the matrix."""
    langs, err = run(f"{SRC}/tree-sitter-xml/grammar.js")
    assert langs == all_languages()
    assert "no languages resolved" in err


@pytest.mark.skipif(SUBMODULES_PRESENT, reason="submodules are initialised here")
def test_uninitialised_submodules_select_everything():
    """Without the upstream grammars the graph is incomplete, so do not narrow.

    This is the dangerous case: tree-sitter-cpp records that it reads
    tree-sitter-c, so with it absent a tree-sitter-c bump would skip cpp.
    """
    assert run(f"{SRC}/tree-sitter-c/src/parser.c")[0] == all_languages()


def test_shared_path_tests_everything():
    """Anything outside the grammar dirs can affect every language."""
    for shared in ["core/src/x.ml", "lang/Makefile", "lang/scripts/list-languages", ".github/x.yml"]:
        assert run(shared)[0] == all_languages(), shared


def test_grammar_change_mixed_with_shared_path_tests_everything():
    assert run(f"{SRC}/semgrep-lua/grammar.js", "lang/Makefile")[0] == all_languages()


def test_no_changed_paths_tests_everything():
    """Fail safe: an empty diff means we could not tell, so run the full matrix."""
    assert run()[0] == all_languages()
