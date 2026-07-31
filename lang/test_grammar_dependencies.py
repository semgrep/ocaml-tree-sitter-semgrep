"""Unit tests for lang/grammar_dependencies."""

from __future__ import annotations

from pathlib import Path

import pytest

from grammar_dependencies import (
    REQUIRED_CROSS_READERS,
    lang_for_upstream,
    languages_affected,
    readers,
    transitive_dependents,
    unpopulated_grammar_dirs,
    upstream_for_lang,
    wrapper_upstream_pairs,
)

LANG_DIR = Path(__file__).resolve().parent
SRC = LANG_DIR / "semgrep-grammars" / "src"
SUBMODULES_PRESENT = not unpopulated_grammar_dirs(SRC)
needs_submodules = pytest.mark.skipif(
    not SUBMODULES_PRESENT, reason="grammar submodules not initialised"
)


def test_go_mod_aliases():
    assert lang_for_upstream("tree-sitter-go-mod") == "gomod"
    assert upstream_for_lang("gomod") == "tree-sitter-go-mod"
    assert lang_for_upstream("tree-sitter-lua") == "lua"
    assert upstream_for_lang("lua") == "tree-sitter-lua"


@needs_submodules
def test_every_wrapper_has_live_upstream_edge():
    """Each semgrep-<lang> must have a live edge from its tree-sitter upstream.

    Covers require(), relative paths, and prep's tree-sitter-\"$name\". Without
    this, languages_affected would rely only on the same-name fallback and a
    renamed upstream (go-mod vs gomod) could silently drop a language.
    """
    edges = readers(SRC)
    pairs = wrapper_upstream_pairs(SRC)
    assert pairs, "expected semgrep-* wrappers under semgrep-grammars/src"
    for semgrep_dir, upstream in pairs:
        lang = semgrep_dir.removeprefix("semgrep-")
        assert (SRC / upstream).is_dir(), f"{semgrep_dir} expects missing {upstream}"
        assert semgrep_dir in edges.get(upstream, set()), (
            f"no live edge {upstream} -> {semgrep_dir}"
        )
        assert lang in languages_affected({upstream}, SRC), (
            f"changing {upstream} must select language {lang!r}"
        )


@needs_submodules
def test_required_cross_grammar_edges():
    """Documented cross-deps (c→cpp, javascript→typescript) stay live.

    typescript's require of javascript lives in common/define-grammar.js, not
    in a file named grammar.js -- so the scan must cover all *.js.
    """
    edges = readers(SRC)
    for upstream, required in REQUIRED_CROSS_READERS.items():
        assert required <= edges.get(upstream, set()), (
            f"{upstream} readers={sorted(edges.get(upstream, set()))}, "
            f"need {sorted(required)}"
        )
    assert languages_affected({"tree-sitter-c"}, SRC) == {"c", "cpp"}
    assert languages_affected({"tree-sitter-javascript"}, SRC) == {
        "javascript",
        "typescript",
    }
    assert languages_affected({"tree-sitter-typescript"}, SRC) == {"typescript"}


@needs_submodules
def test_c_is_read_by_cpp_not_comment_only_solidity():
    """Live edges only: cpp requires c; solidity's URL comment must not count."""
    assert readers(SRC)["tree-sitter-c"] >= {
        "semgrep-c",
        "tree-sitter-cpp",
    }
    assert "tree-sitter-solidity" not in readers(SRC)["tree-sitter-c"]
    assert "semgrep-cpp" not in readers(SRC).get("tree-sitter-c", set())


@needs_submodules
def test_javascript_and_typescript_are_linked_one_way():
    """typescript reads javascript (via common/define-grammar.js, not grammar.js);
    javascript does not read typescript. languages_affected for both sides is
    covered by test_required_cross_grammar_edges."""
    assert "tree-sitter-typescript" in readers(SRC)["tree-sitter-javascript"]
    assert "tree-sitter-javascript" not in readers(SRC).get("tree-sitter-typescript", set())


@needs_submodules
def test_prep_name_ref_links_powershell_and_c_sharp_pro():
    """Wrappers that only use tree-sitter-\"$name\" still get a live edge."""
    assert "semgrep-powershell" in readers(SRC)["tree-sitter-powershell"]
    assert "semgrep-c-sharp-pro" in readers(SRC)["tree-sitter-c-sharp-pro"]


@needs_submodules
def test_transitive_dependents_follow_reader_edges():
    deps = transitive_dependents({"tree-sitter-c"}, SRC)
    assert {"tree-sitter-c", "tree-sitter-cpp"} <= deps
    assert {"semgrep-c", "semgrep-cpp"} <= deps
    assert "tree-sitter-solidity" not in deps


@needs_submodules
def test_languages_affected_filters_to_semgrep_langs():
    assert languages_affected({"tree-sitter-c"}, SRC) == {"c", "cpp"}
    assert languages_affected({"tree-sitter-c-sharp"}, SRC) == {"c-sharp"}
    assert languages_affected({"tree-sitter-c-sharp-pro"}, SRC) == {"c-sharp-pro"}
    assert languages_affected({"tree-sitter-powershell"}, SRC) == {"powershell"}
    assert languages_affected({"tree-sitter-go-mod"}, SRC) == {"gomod"}
    # Comment-only mention of tree-sitter-xml in html must not create an edge;
    # same-name fallback does not apply (no semgrep-xml).
    assert languages_affected({"tree-sitter-xml"}, SRC) == set()
