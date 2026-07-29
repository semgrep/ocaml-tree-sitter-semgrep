"""Unit tests for lang/scripts/list-languages."""

from __future__ import annotations

import subprocess
from pathlib import Path

LANG_DIR = Path(__file__).resolve().parent
SCRIPT = LANG_DIR / "scripts" / "list-languages"


def _run() -> list[str]:
    proc = subprocess.run([SCRIPT], capture_output=True, text=True, check=True)
    return proc.stdout.splitlines()


def test_list_languages_excludes_nested_sub_dialects():
    """Lists cfml/sfapex but not their nested sub-dialects."""
    langs = _run()
    assert "cfml" in langs
    assert "sfapex" in langs
    assert "cfquery" not in langs
    assert "cfscript" not in langs
    assert "soql" not in langs
    assert "sosl" not in langs
    assert langs == sorted(langs)


def test_list_languages_usage_error():
    """Exits 2 (argparse) on an unexpected argument."""
    proc = subprocess.run([SCRIPT, "--bogus"], capture_output=True, text=True)
    assert proc.returncode == 2
