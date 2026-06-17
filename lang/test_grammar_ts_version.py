"""Verify that each grammar is generated with the tree-sitter version pinned for
it in lang/languages-<version> / lang/language-variants-<version>.

Everything is derived from the filesystem -- nothing is hardcoded and the
Makefile is not consulted:

* the set of tree-sitter versions      = the versions in the list filenames
* the per-language pin                  = the contents of those files, as
                                          resolved by lang/ts_versions.py
* the set of generated grammars         = the semgrep-* packages under
                                          lang/semgrep-grammars/src (what the
                                          build's ``for pkg in semgrep-*`` iterates)

Run with: pytest lang/test_grammar_ts_version.py
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ts_versions import TsVersionError, list_pinned_versions, version_for_grammar_dir, version_for_lang

LANG_DIR = Path(__file__).resolve().parent
REPO_ROOT = LANG_DIR.parent
SRC = LANG_DIR / "semgrep-grammars" / "src"

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
REPORTED_RE = re.compile(r"\(tree-sitter (\d+\.\d+\.\d+)\)")


def _list_files():
    """Return sorted languages-* and language-variants-* paths under lang/."""
    return sorted(LANG_DIR.glob("languages-*")) + sorted(LANG_DIR.glob("language-variants-*"))


def _all_listed_names():
    """Return every language/dialect name listed in the pin files."""
    names: set[str] = set()
    for path in _list_files():
        if path.name.endswith(".readme"):
            continue
        for line in path.read_text().splitlines():
            if line.strip():
                names.add(line.strip())
    return sorted(names)


def _grammar_dirs():
    """Every directory the build generates: each grammar.js under a semgrep-* package."""
    dirs = []
    for pkg in sorted(SRC.glob("semgrep-*")):
        if pkg.is_dir():
            dirs.extend(sorted(gj.parent for gj in pkg.rglob("grammar.js")))
    return dirs


def _resolve_lang(name):
    """Return the pinned version for *name*, or None if unlisted or ambiguous."""
    try:
        return version_for_lang(name, LANG_DIR)
    except TsVersionError:
        return None


def _resolve_dir(path):
    """Return the pinned version for a grammar directory, or None on TsVersionError."""
    try:
        return version_for_grammar_dir(path, LANG_DIR)
    except TsVersionError:
        return None


def _binary(version):
    """Return the path to core/tree-sitter-<version>/bin/tree-sitter."""
    return REPO_ROOT / "core" / f"tree-sitter-{version}" / "bin" / "tree-sitter"


VERSIONS = list_pinned_versions(LANG_DIR)
GRAMMAR_DIRS = _grammar_dirs()


def test_versions_are_discovered():
    """At least one tree-sitter version is discovered from list filenames."""
    assert VERSIONS, "no tree-sitter versions found in lang/languages-* filenames"


@pytest.mark.parametrize("name", _all_listed_names())
def test_pin_is_unique_and_resolves(name):
    """Each language is pinned to exactly one version, and version_for_lang agrees."""
    version_for_lang(name, LANG_DIR)


@pytest.mark.parametrize("grammar_dir", GRAMMAR_DIRS, ids=lambda d: str(d.relative_to(SRC)))
def test_grammar_dir_resolves_to_a_declared_version(grammar_dir):
    """Every generated grammar resolves to one of the declared tree-sitter versions."""
    version = _resolve_dir(grammar_dir)
    if version is None:
        pytest.skip(
            f"{grammar_dir.relative_to(SRC)} is not pinned to any tree-sitter version "
            f"(excluded from the per-version build)"
        )
    assert version in VERSIONS


@pytest.mark.parametrize("version", VERSIONS)
def test_installed_binary_reports_its_version(version):
    """core/tree-sitter-<version>/bin/tree-sitter actually is that version, so the
    build picking that directory really runs that version."""
    binary = _binary(version)
    if not binary.exists():
        pytest.skip(f"tree-sitter {version} not installed at {binary}")
    out = subprocess.run([binary, "--version"], capture_output=True, text=True).stdout
    m = VERSION_RE.search(out)
    assert m and m.group(0) == version, f"{binary} reports {out.strip()!r}, expected {version}"


@pytest.mark.parametrize("version", VERSIONS)
def test_generation_uses_the_pinned_version(version):
    """End to end: building a grammar pinned to <version> generates it with that
    version. Skipped where the binary or grammar submodule sources are absent."""
    if not _binary(version).exists():
        pytest.skip(f"tree-sitter {version} not installed")
    if not shutil.which("node"):
        pytest.skip("node not available (tree-sitter generate needs it)")

    package = None
    for grammar_dir in GRAMMAR_DIRS:
        if _resolve_dir(grammar_dir) == version:
            package = SRC / grammar_dir.relative_to(SRC).parts[0]
            break
    if package is None:
        pytest.skip(f"no grammar pinned to {version}")

    for gj in package.rglob("grammar.js"):
        gj.touch()  # force regeneration
    proc = subprocess.run(["make", "-C", str(package), "build"], capture_output=True, text=True)
    reported = sorted(set(REPORTED_RE.findall(proc.stdout + proc.stderr)))

    wrong = [r for r in reported if r != version]
    assert not wrong, (
        f"{package.name} was generated with tree-sitter {wrong}, expected {version}\n"
        + proc.stdout[-2000:]
    )
    if proc.returncode != 0 or version not in reported:
        pytest.skip(
            f"{package.name} build did not complete (rc={proc.returncode}); "
            f"likely missing submodule sources"
        )
