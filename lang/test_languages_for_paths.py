"""Unit tests for lang/scripts/languages-for-paths."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

LANG_DIR = Path(__file__).resolve().parent
SCRIPT = LANG_DIR / "scripts" / "languages-for-paths"
SRC = "lang/semgrep-grammars/src"

# The reference graph is read out of the upstream grammars, so narrowing only
# works when the submodules are checked out. Without them the script must fall
# back to the full matrix -- asserted by test_uninitialised_submodules_* below.
GRAMMARS = LANG_DIR / "semgrep-grammars" / "src"
SUBMODULES_PRESENT = not [
    d
    for d in GRAMMARS.glob("tree-sitter-*")
    if d.is_dir() and not any(p.name[0] != "." for p in d.iterdir())
]
needs_submodules = pytest.mark.skipif(
    not SUBMODULES_PRESENT, reason="grammar submodules not initialised"
)


def run(*paths: str) -> list[str]:
    proc = subprocess.run(
        [SCRIPT], input="\n".join(paths), capture_output=True, text=True, check=True
    )
    return proc.stdout.split()


def all_languages() -> list[str]:
    return subprocess.run(
        [LANG_DIR / "scripts" / "list-languages"], capture_output=True, text=True, check=True
    ).stdout.split()


@needs_submodules
def test_language_own_dir_narrows_to_that_language():
    assert run(f"{SRC}/semgrep-lua/grammar.js") == ["lua"]


@needs_submodules
def test_follows_references_between_grammars():
    """tree-sitter-c is read by cpp and solidity, not just c."""
    assert set(run(f"{SRC}/tree-sitter-c/src/parser.c")) >= {"c", "cpp", "solidity"}
    assert set(run(f"{SRC}/tree-sitter-c-sharp/grammar.js")) >= {"c-sharp", "c-sharp-pro"}


@needs_submodules
def test_upstream_dir_without_a_language_of_its_own():
    """tree-sitter-xml has no semgrep-xml; it is only reachable via html."""
    assert run(f"{SRC}/tree-sitter-xml/grammar.js") == ["html"]


@pytest.mark.skipif(SUBMODULES_PRESENT, reason="submodules are initialised here")
def test_uninitialised_submodules_select_everything():
    """Without the upstream grammars the graph is incomplete, so do not narrow.

    This is the dangerous case: tree-sitter-solidity records that it reads
    tree-sitter-c, so with it absent a tree-sitter-c bump would skip solidity.
    """
    assert run(f"{SRC}/tree-sitter-c/src/parser.c") == all_languages()


def test_shared_path_tests_everything():
    """Anything outside the grammar dirs can affect every language."""
    for shared in ["core/src/x.ml", "lang/Makefile", "lang/scripts/list-languages", ".github/x.yml"]:
        assert run(shared) == all_languages(), shared


def test_grammar_change_mixed_with_shared_path_tests_everything():
    assert run(f"{SRC}/semgrep-lua/grammar.js", "lang/Makefile") == all_languages()


def test_no_changed_paths_tests_everything():
    """Fail safe: an empty diff means we could not tell, so run the full matrix."""
    assert run() == all_languages()
