"""Select ``tree-sitter generate`` ABI flags for a grammar directory.

Rules:
- ``--abi=15`` only when the grammar dir has a ``tree-sitter.json`` and
  ``SEMGREP_ENABLE_ABI15`` is truthy. ABI 15 requires tree-sitter >= 0.25.0.
  Off by default: we are not yet ready to ship ABI 15 parsers.
- ``--abi=14`` for tree-sitter >= 0.24.0 (the release that introduced ``--abi``).
- ``--no-bindings`` for older tree-sitter.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from ts_versions import version_at_least

ABI15_TRUTHY = frozenset({"1", "true", "TRUE", "yes", "YES", "on", "ON"})


class GenerateAbiError(RuntimeError):
    """ABI 15 was requested but the pinned tree-sitter version is too old."""


def abi15_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return True when ``SEMGREP_ENABLE_ABI15`` is set to a truthy value."""
    source = os.environ if env is None else env
    return source.get("SEMGREP_ENABLE_ABI15", "") in ABI15_TRUTHY


def generate_abi_args(
    grammar_dir: Path | str,
    ts_version: str,
    *,
    env: Mapping[str, str] | None = None,
) -> str:
    """Return the ``tree-sitter generate`` flag for a grammar and tree-sitter version."""
    directory = Path(grammar_dir)
    if (directory / "tree-sitter.json").is_file() and abi15_enabled(env):
        if not version_at_least(ts_version, "0.25.0"):
            raise GenerateAbiError(
                f"Error: {directory} uses ABI 15 (tree-sitter.json present, "
                f"SEMGREP_ENABLE_ABI15 set) and requires tree-sitter >= 0.25.0, "
                f"but this grammar is pinned to {ts_version}."
            )
        return "--abi=15"
    if version_at_least(ts_version, "0.24.0"):
        return "--abi=14"
    return "--no-bindings"


def main_ts_generate_abi_args(argv: list[str] | None = None) -> int:
    """CLI entry point: print ABI args for a grammar dir and tree-sitter version."""
    args = argv if argv is not None else sys.argv
    if len(args) != 3:
        print(f"Usage: {Path(args[0]).name} <grammar-dir> <tree-sitter-version>", file=sys.stderr)
        return 2
    try:
        print(generate_abi_args(args[1], args[2]))
    except GenerateAbiError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
