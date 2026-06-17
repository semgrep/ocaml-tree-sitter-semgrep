"""Tree-sitter version resolution for per-language grammar builds.

The mapping lives in ``lang/languages-<version>`` and
``lang/language-variants-<version>`` files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
LIST_FILE_PREFIXES = ("languages-", "language-variants-")
JSON_NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')


class TsVersionError(LookupError):
    """A language or grammar directory has no unique tree-sitter version pin."""


def default_lang_dir() -> Path:
    """Return the ``lang/`` directory containing version list files."""
    return Path(__file__).resolve().parent


def version_sort_key(version: str) -> tuple[int, ...]:
    """Return a comparable tuple for semver-like version strings."""
    return tuple(int(part) for part in version.split("."))


def version_at_least(version: str, minimum: str) -> bool:
    """Return True when *version* is greater than or equal to *minimum*."""
    return version_sort_key(version) >= version_sort_key(minimum)


def _list_pin_files(lang_dir: Path) -> list[Path]:
    """Return sorted ``languages-*`` and ``language-variants-*`` paths under *lang_dir*."""
    return sorted(lang_dir.glob("languages-*")) + sorted(lang_dir.glob("language-variants-*"))


def _version_from_list_filename(path: Path) -> str | None:
    """Extract the version suffix from a list filename, or None if unrecognized."""
    for prefix in LIST_FILE_PREFIXES:
        if path.name.startswith(prefix):
            return path.name[len(prefix) :]
    return None


def list_pinned_versions(lang_dir: Path | None = None) -> list[str]:
    """Return distinct tree-sitter versions from languages-* list filenames."""
    root = lang_dir or default_lang_dir()
    versions: set[str] = set()
    for path in _list_pin_files(root):
        if not path.is_file():
            continue
        match = VERSION_RE.search(path.name)
        if match:
            versions.add(match.group(0))
    return sorted(versions, key=version_sort_key)


def version_for_lang(name: str, lang_dir: Path | None = None) -> str:
    """Return the tree-sitter version pinned for a language or dialect name."""
    root = lang_dir or default_lang_dir()
    matches: list[str] = []
    for path in _list_pin_files(root):
        if path.name.endswith(".readme") or not path.is_file():
            continue
        version = _version_from_list_filename(path)
        if version is None:
            continue
        for line in path.read_text().splitlines():
            if line.strip() == name:
                matches.append(version)
                break
    unique = sorted(set(matches), key=version_sort_key)
    if not unique:
        raise TsVersionError(
            f"Error: '{name}' is not listed in any {root}/languages-* or "
            f"{root}/language-variants-* file.\n"
            "Add it to the file matching the tree-sitter version it should use."
        )
    if len(unique) > 1:
        raise TsVersionError(
            f"Error: '{name}' resolves to multiple tree-sitter versions:\n"
            + "\n".join(unique)
        )
    return unique[0]


def extract_grammar_name(grammar_dir: Path) -> str:
    """Infer the language name for a grammar directory."""
    resolved = grammar_dir.resolve()
    for rel in ("tree-sitter.json", "src/grammar.json"):
        json_file = resolved / rel
        if not json_file.is_file():
            continue
        match = JSON_NAME_RE.search(json_file.read_text())
        if match:
            name = match.group(1)
            break
    else:
        name = resolved.name
        for prefix in ("tree-sitter-", "semgrep-"):
            if name.startswith(prefix):
                name = name[len(prefix) :]
    return name.replace("_", "-")


def version_for_grammar_dir(grammar_dir: Path | str, lang_dir: Path | None = None) -> str:
    """Return the tree-sitter version pinned for a grammar directory."""
    return version_for_lang(extract_grammar_name(Path(grammar_dir)), lang_dir)


def main_ts_versions() -> int:
    """CLI entry point: print each pinned tree-sitter version on its own line."""
    for version in list_pinned_versions():
        print(version)
    return 0


def main_ts_version_for_lang(argv: list[str] | None = None) -> int:
    """CLI entry point: print the tree-sitter version for a language name."""
    args = argv if argv is not None else sys.argv
    if len(args) != 2:
        print(f"Usage: {args[0]} <lang>", file=sys.stderr)
        return 2
    try:
        print(version_for_lang(args[1]))
    except TsVersionError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


def main_ts_version_for_grammar_dir(argv: list[str] | None = None) -> int:
    """CLI entry point: print the tree-sitter version for a grammar directory."""
    args = argv if argv is not None else sys.argv
    if len(args) != 2:
        print(f"Usage: {args[0]} <grammar-dir>", file=sys.stderr)
        return 2
    try:
        print(version_for_grammar_dir(args[1]))
    except TsVersionError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
