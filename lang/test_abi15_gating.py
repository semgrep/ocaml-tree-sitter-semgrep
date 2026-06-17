"""Test ABI selection for tree-sitter generate (SEMGREP_ENABLE_ABI15 gating).

Layer 1 exercises ``lang/scripts/ts-generate-abi-args`` (decision table).
Layer 2 verifies the env var actually changes ``LANGUAGE_VERSION`` in
``parser.c`` when running ``tree-sitter generate`` (requires tree-sitter
>= 0.25.0 and node).

Run with: pytest lang/test_abi15_gating.py
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

LANG_DIR = Path(__file__).resolve().parent
REPO_ROOT = LANG_DIR.parent
ABI_ARGS_SCRIPT = LANG_DIR / "scripts" / "ts-generate-abi-args"

LANGUAGE_VERSION_RE = re.compile(r"^#define LANGUAGE_VERSION (\d+)", re.MULTILINE)
VERSION_RE = re.compile(r"tree-sitter (\d+\.\d+\.\d+)")

GRAMMAR_JS = """\
module.exports = grammar({
  name: 'abitest',
  rules: {
    source_file: $ => repeat($.word),
    word: $ => /[a-z]+/,
  },
});
"""

TREE_SITTER_JSON = """\
{
  "grammars": [{ "name": "abitest", "scope": "source.abitest", "path": "." }],
  "metadata": { "version": "0.0.0", "license": "MIT", "description": "ABI gating test grammar" },
  "bindings": { "c": true, "go": false, "node": false, "python": false, "rust": false, "swift": false }
}
"""


def _run_abi_args(grammar_dir: Path, ts_version: str, *, abi15: str | None = None) -> str:
    """Run ts-generate-abi-args; abi15=None means leave env unset."""
    env = os.environ.copy()
    if abi15 is None:
        env.pop("SEMGREP_ENABLE_ABI15", None)
    else:
        env["SEMGREP_ENABLE_ABI15"] = abi15
    proc = subprocess.run(
        [ABI_ARGS_SCRIPT, str(grammar_dir), ts_version],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _version_at_least(version: str, minimum: str) -> bool:
    proc = subprocess.run(
        ["sort", "-V", "-C"],
        input=f"{minimum}\n{version}\n",
        text=True,
        capture_output=True,
    )
    return proc.returncode == 0


def _default_tree_sitter_bin() -> Path | None:
    override = os.environ.get("TREE_SITTER_BIN")
    if override:
        path = Path(override)
        return path if path.is_file() and os.access(path, os.X_OK) else None
    candidate = REPO_ROOT / "core" / "tree-sitter-0.26.3" / "bin" / "tree-sitter"
    return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None


def _reported_version(ts_bin: Path) -> str | None:
    proc = subprocess.run([ts_bin, "--version"], capture_output=True, text=True)
    m = VERSION_RE.search(proc.stdout)
    return m.group(1) if m else None


def _generate_and_read_language_version(
    grammar_dir: Path,
    ts_bin: Path,
    ts_version: str,
    *,
    abi15: str | None = None,
) -> str | None:
    parser_c = grammar_dir / "src" / "parser.c"
    if parser_c.exists():
        parser_c.unlink()
    args = _run_abi_args(grammar_dir, ts_version, abi15=abi15)
    env = os.environ.copy()
    if abi15 is None:
        env.pop("SEMGREP_ENABLE_ABI15", None)
    else:
        env["SEMGREP_ENABLE_ABI15"] = abi15
    env["PATH"] = f"{ts_bin.parent}:{env.get('PATH', '')}"
    proc = subprocess.run(
        ["tree-sitter", "generate", *args.split()],
        cwd=grammar_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = parser_c.read_text()
    m = LANGUAGE_VERSION_RE.search(text)
    return m.group(1) if m else None


@pytest.fixture
def grammar_dirs(tmp_path):
    with_json = tmp_path / "with-json"
    without_json = tmp_path / "without-json"
    with_json.mkdir()
    without_json.mkdir()
    (with_json / "tree-sitter.json").write_text("{}")
    return with_json, without_json


@pytest.mark.parametrize(
    "has_json,ts_version,abi15,expected",
    [
        (True, "0.26.3", "1", "--abi=15"),
        (True, "0.26.3", None, "--abi=14"),
        (True, "0.26.3", "0", "--abi=14"),
        (True, "0.26.3", "false", "--abi=14"),
        (False, "0.26.3", "1", "--abi=14"),
        (False, "0.24.0", None, "--abi=14"),
        (False, "0.20.8", None, "--no-bindings"),
    ],
    ids=[
        "json+abi15-on",
        "json+abi15-unset",
        "json+abi15=0",
        "json+abi15=false",
        "no-json+abi15-on",
        "no-json-0.24.0",
        "no-json-0.20.8",
    ],
)
def test_ts_generate_abi_args(grammar_dirs, has_json, ts_version, abi15, expected):
    """ts-generate-abi-args returns the expected flag for each input combination."""
    with_json, without_json = grammar_dirs
    grammar_dir = with_json if has_json else without_json
    assert _run_abi_args(grammar_dir, ts_version, abi15=abi15) == expected


def test_abi15_env_var_flips_generated_language_version(tmp_path):
    """SEMGREP_ENABLE_ABI15 changes LANGUAGE_VERSION in generated parser.c."""
    ts_bin = _default_tree_sitter_bin()
    if ts_bin is None:
        pytest.skip(
            "tree-sitter >= 0.25.0 not installed "
            f"(looked for TREE_SITTER_BIN or {REPO_ROOT / 'core/tree-sitter-0.26.3/bin/tree-sitter'})"
        )
    ts_version = _reported_version(ts_bin)
    if ts_version is None or not _version_at_least(ts_version, "0.25.0"):
        pytest.skip(f"tree-sitter {ts_version!r} at {ts_bin} does not support ABI 15")
    if shutil.which("node") is None:
        pytest.skip("node not available (tree-sitter generate needs it)")

    grammar_dir = tmp_path / "grammar"
    grammar_dir.mkdir()
    (grammar_dir / "grammar.js").write_text(GRAMMAR_JS)
    (grammar_dir / "tree-sitter.json").write_text(TREE_SITTER_JSON)

    abi_off = _generate_and_read_language_version(grammar_dir, ts_bin, ts_version, abi15=None)
    abi_on = _generate_and_read_language_version(grammar_dir, ts_bin, ts_version, abi15="1")

    assert abi_off == "14"
    assert abi_on == "15"
    assert abi_off != abi_on
