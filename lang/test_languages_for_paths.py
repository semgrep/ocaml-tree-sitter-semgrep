"""Unit tests for lang/scripts/languages-for-paths."""

from __future__ import annotations

import subprocess
from pathlib import Path

LANG_DIR = Path(__file__).resolve().parent
SCRIPT = LANG_DIR / "scripts" / "languages-for-paths"
SRC = "lang/semgrep-grammars/src"


def run(*paths: str) -> list[str]:
    proc = subprocess.run(
        [SCRIPT], input="\n".join(paths), capture_output=True, text=True, check=True
    )
    return proc.stdout.split()


def all_languages() -> list[str]:
    return subprocess.run(
        [LANG_DIR / "scripts" / "list-languages"], capture_output=True, text=True, check=True
    ).stdout.split()


def test_language_own_dir_narrows_to_that_language():
    assert run(f"{SRC}/semgrep-lua/grammar.js") == ["lua"]


def test_follows_references_between_grammars():
    """tree-sitter-c is read by cpp and solidity, not just c."""
    assert set(run(f"{SRC}/tree-sitter-c/src/parser.c")) >= {"c", "cpp", "solidity"}
    assert set(run(f"{SRC}/tree-sitter-c-sharp/grammar.js")) >= {"c-sharp", "c-sharp-pro"}


def test_upstream_dir_without_a_language_of_its_own():
    """tree-sitter-xml has no semgrep-xml; it is only reachable via html."""
    assert run(f"{SRC}/tree-sitter-xml/grammar.js") == ["html"]


def test_shared_path_tests_everything():
    """Anything outside the grammar dirs can affect every language."""
    for shared in ["core/src/x.ml", "lang/Makefile", "lang/scripts/list-languages", ".github/x.yml"]:
        assert run(shared) == all_languages(), shared


def test_grammar_change_mixed_with_shared_path_tests_everything():
    assert run(f"{SRC}/semgrep-lua/grammar.js", "lang/Makefile") == all_languages()


def test_no_changed_paths_tests_everything():
    """Fail safe: an empty diff means we could not tell, so run the full matrix."""
    assert run() == all_languages()
