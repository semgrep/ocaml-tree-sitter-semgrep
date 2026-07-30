"""Unit tests for lang/scripts/list-languages."""

from __future__ import annotations

import subprocess
from pathlib import Path

LANG_DIR = Path(__file__).resolve().parent
SCRIPT = LANG_DIR / "scripts" / "list-languages"


def test_list_languages_excludes_nested_sub_dialects():
    """Lists cfml/sfapex but not the sub-dialects nested inside their dirs."""
    proc = subprocess.run([SCRIPT], capture_output=True, text=True, check=True)
    langs = proc.stdout.splitlines()
    assert {"cfml", "sfapex"} <= set(langs)
    assert not {"cfquery", "cfscript", "soql", "sosl"} & set(langs)
