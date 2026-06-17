"""Unit tests for lang/ts_versions.py and its CLI entry points."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ts_versions import (
    TsVersionError,
    extract_grammar_name,
    list_pinned_versions,
    main_ts_version_for_grammar_dir,
    main_ts_version_for_lang,
    version_for_grammar_dir,
    version_for_lang,
    version_sort_key,
)

LANG_DIR = Path(__file__).resolve().parent
SCRIPTS = LANG_DIR / "scripts"


def test_list_pinned_versions_matches_repo():
    """list_pinned_versions returns a non-empty, semver-sorted version list."""
    versions = list_pinned_versions(LANG_DIR)
    assert versions
    assert versions == sorted(versions, key=version_sort_key)


def test_version_for_lang_known_language():
    """Known languages resolve to their pinned tree-sitter versions."""
    assert version_for_lang("php", LANG_DIR) == "0.26.3"
    assert version_for_lang("scala", LANG_DIR) == "0.22.6"


def test_version_for_lang_missing(tmp_path):
    """version_for_lang raises TsVersionError when the name is not listed."""
    (tmp_path / "languages-0.22.6").write_text("kotlin\n")
    with pytest.raises(TsVersionError, match="not listed"):
        version_for_lang("missing", tmp_path)


def test_version_for_lang_ambiguous(tmp_path):
    """version_for_lang raises TsVersionError when listed under multiple versions."""
    (tmp_path / "languages-0.22.6").write_text("kotlin\n")
    (tmp_path / "languages-0.26.3").write_text("kotlin\n")
    with pytest.raises(TsVersionError, match="multiple tree-sitter versions"):
        version_for_lang("kotlin", tmp_path)


def test_extract_grammar_name_from_tree_sitter_json(tmp_path):
    """extract_grammar_name reads the name from tree-sitter.json."""
    grammar_dir = tmp_path / "php_only"
    grammar_dir.mkdir()
    (grammar_dir / "tree-sitter.json").write_text(
        '{"grammars": [{"name": "php_only", "scope": "source.php", "path": "."}]}'
    )
    assert extract_grammar_name(grammar_dir) == "php-only"


def test_extract_grammar_name_from_directory_basename(tmp_path):
    """extract_grammar_name falls back to the directory basename with prefix stripping."""
    grammar_dir = tmp_path / "semgrep-scala"
    grammar_dir.mkdir()
    assert extract_grammar_name(grammar_dir) == "scala"


def test_version_for_grammar_dir_delegates_to_lang_pins(tmp_path):
    """version_for_grammar_dir resolves via the grammar name and lang pin files."""
    (tmp_path / "languages-0.26.3").write_text("php\n")
    grammar_dir = tmp_path / "semgrep-php" / "php"
    grammar_dir.mkdir(parents=True)
    (grammar_dir / "tree-sitter.json").write_text(
        '{"grammars": [{"name": "php", "scope": "source.php", "path": "."}]}'
    )
    assert version_for_grammar_dir(grammar_dir, lang_dir=tmp_path) == "0.26.3"


@pytest.mark.parametrize(
    "script,args,expected",
    [
        ("ts-versions", [], None),
        ("ts-version-for-lang", ["php"], "0.26.3\n"),
        ("ts-version-for-grammar-dir", [str(LANG_DIR / "semgrep-grammars/src/semgrep-php/php")], "0.26.3\n"),
    ],
)
def test_cli_entry_points(script, args, expected):
    """CLI wrapper scripts print the expected version output."""
    proc = subprocess.run([SCRIPTS / script, *args], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    if expected is None:
        assert proc.stdout.strip()
    else:
        assert proc.stdout == expected


def test_cli_usage_errors():
    """CLI entry points return exit code 2 when given no arguments."""
    assert main_ts_version_for_lang(["ts-version-for-lang"]) == 2
    assert main_ts_version_for_grammar_dir(["ts-version-for-grammar-dir"]) == 2
