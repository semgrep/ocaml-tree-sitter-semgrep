"""Grammar reference graph for ``lang/semgrep-grammars/src``.

Used by ``languages-for-paths`` to decide which ``./test-lang`` targets a
diff can affect. The graph is derived from the grammars themselves so it
cannot drift from what the build actually loads.

Edge discovery (live code only; comments are stripped first)
-----------------------------------------------------------
1. Any ``tree-sitter-<x>`` token in a ``*.js`` or ``prep`` file under a
   ``semgrep-*`` / ``tree-sitter-*`` dir creates an edge
   ``tree-sitter-<x> -> that dir``.
2. A ``prep`` script that builds paths as ``tree-sitter-"$name"`` (or
   ``tree-sitter-$name``) edges to that wrapper's upstream
   (``upstream_for_lang``), so powershell / c-sharp-pro are covered even
   without a literal ``require('tree-sitter-…')``.
3. ``languages_affected`` then walks those edges transitively and, for every
   reached ``tree-sitter-X``, also includes language ``X`` when
   ``semgrep-X`` exists (``UPSTREAM_TO_LANG`` covers ``go-mod`` / ``gomod``).

JS comment stripping is line-based and does not respect string literals, so a
``"… // …"`` (or ``https://…``) can truncate the rest of that line. No current
grammar puts a ``require('tree-sitter-…')`` after such a string on the same
line; the same-name fallback still covers each wrapper's primary upstream.

Invariants (enforced by ``test_grammar_dependencies``)
------------------------------------------------------
- Every ``semgrep-<lang>`` has a live reader edge from its upstream dir.
- Changing that upstream always selects ``<lang>`` (same-name / alias).
- Documented cross-grammar edges stay live (not comment-only)::

      tree-sitter-c            -> tree-sitter-cpp   (hence language cpp)
      tree-sitter-javascript   -> tree-sitter-typescript  (hence typescript)

  So a JS upstream bump retests typescript; a TS bump does not retest
  javascript.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

# Relative to the repo root.
GRAMMARS_SUBDIR = "lang/semgrep-grammars/src"

# Appears in package.json devDependencies of nearly every upstream grammar.
NOT_A_GRAMMAR = frozenset({"cli"})

# tree-sitter-<suffix> dir <-> semgrep-<lang> when the names differ.
UPSTREAM_TO_LANG = {"go-mod": "gomod"}
LANG_TO_UPSTREAM = {v: k for k, v in UPSTREAM_TO_LANG.items()}

# Cross-grammar edges the matrix relies on. Values are reader *dirs* that must
# appear in readers()[key] via a live reference (see module docstring).
REQUIRED_CROSS_READERS: dict[str, frozenset[str]] = {
    "tree-sitter-c": frozenset({"tree-sitter-cpp"}),
    "tree-sitter-javascript": frozenset({"tree-sitter-typescript"}),
}

GRAMMAR_REF = re.compile(r"tree-sitter-([a-z0-9_-]+)")
# prep.common and friends build paths as tree-sitter-"$name" / tree-sitter-$name.
# "$name" ends on a quote, so \b cannot follow the quoted form.
PREP_NAME_REF = re.compile(r"""tree-sitter-(?:"\$name"|\$name\b)""")

_JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_JS_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)
_SH_LINE_COMMENT = re.compile(r"#.*?$", re.MULTILINE)


def default_grammars_src() -> Path:
    """Return ``lang/semgrep-grammars/src`` next to this module."""
    return Path(__file__).resolve().parent / "semgrep-grammars" / "src"


def _strip_js_comments(text: str) -> str:
    return _JS_LINE_COMMENT.sub("", _JS_BLOCK_COMMENT.sub("", text))


def _strip_sh_comments(text: str) -> str:
    return _SH_LINE_COMMENT.sub("", text)


def lang_for_upstream(tree_sitter_dir: str) -> str:
    """Map ``tree-sitter-X`` dir name to the standalone language name."""
    suffix = tree_sitter_dir.removeprefix("tree-sitter-")
    return UPSTREAM_TO_LANG.get(suffix, suffix)


def upstream_for_lang(lang: str) -> str:
    """Map standalone language name to ``tree-sitter-X`` dir name."""
    return f"tree-sitter-{LANG_TO_UPSTREAM.get(lang, lang)}"


def wrapper_upstream_pairs(src: Path | None = None) -> list[tuple[str, str]]:
    """Return ``(semgrep-<lang>, tree-sitter-…)`` for every wrapper under *src*."""
    root = src or default_grammars_src()
    pairs: list[tuple[str, str]] = []
    for d in sorted(root.glob("semgrep-*")):
        if d.is_dir():
            lang = d.name.removeprefix("semgrep-")
            pairs.append((d.name, upstream_for_lang(lang)))
    return pairs


def readers(src: Path | None = None) -> dict[str, set[str]]:
    """Map ``tree-sitter-<x>`` -> dirs with a live ``.js``/``prep`` reference."""
    root = src or default_grammars_src()
    out: dict[str, set[str]] = defaultdict(set)
    for d in root.glob("*/"):
        if not d.name.startswith(("semgrep-", "tree-sitter-")):
            continue
        for f in [*d.rglob("*.js"), *d.rglob("prep")]:
            try:
                raw = f.read_text(errors="ignore")
            except OSError:
                continue
            is_prep = f.name == "prep"
            text = _strip_sh_comments(raw) if is_prep else _strip_js_comments(raw)
            for ref in GRAMMAR_REF.findall(text):
                if ref in NOT_A_GRAMMAR or f"tree-sitter-{ref}" == d.name:
                    continue
                out[f"tree-sitter-{ref}"].add(d.name)
            if is_prep and PREP_NAME_REF.search(text) and d.name.startswith("semgrep-"):
                lang = d.name.removeprefix("semgrep-")
                out[upstream_for_lang(lang)].add(d.name)
    return out


def transitive_dependents(dirs: set[str], src: Path | None = None) -> set[str]:
    """Grammar dirs reachable by following reader edges from *dirs* (inclusive)."""
    edges = readers(src)
    seen: set[str] = set()
    queue = list(dirs)
    while queue:
        d = queue.pop()
        if d in seen:
            continue
        seen.add(d)
        queue.extend(edges.get(d, set()) - seen)
    return seen


def languages_affected(dirs: set[str], src: Path | None = None) -> set[str]:
    """Standalone languages affected by changes in *dirs*, following references."""
    root = src or default_grammars_src()
    deps = transitive_dependents(dirs, src)
    langs = {
        d.removeprefix("semgrep-") for d in deps if d.startswith("semgrep-")
    }
    for d in deps:
        if not d.startswith("tree-sitter-"):
            continue
        lang = lang_for_upstream(d)
        if (root / f"semgrep-{lang}").is_dir():
            langs.add(lang)
    return langs


def unpopulated_grammar_dirs(src: Path | None = None) -> list[str]:
    """Upstream dirs with no checked-out content (submodule not initialised).

    Edges live inside the upstream grammars, so an uninitialised submodule makes
    the graph silently incomplete: without ``tree-sitter-cpp`` checked out,
    nothing records that it reads ``tree-sitter-c``. Callers that need a
    complete graph must treat a non-empty result as "cannot trust the edges".
    """
    root = src or default_grammars_src()

    def has_content(d: Path) -> bool:
        # Dotfiles only (a stray .git) do not count: nothing to read edges from.
        return any(p.name[0] != "." for p in d.iterdir())

    return sorted(
        d.name for d in root.glob("tree-sitter-*") if d.is_dir() and not has_content(d)
    )
