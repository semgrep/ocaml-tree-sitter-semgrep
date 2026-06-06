"""Unit tests for scripts/propose-grammar-update.

Mirrors scripts/test_update_grammar.py: load the extensionless driver via
SourceFileLoader, then test its pure logic (tag parsing/sorting, URL
rewrite, version mapping, PR-body shaping). Git/network-dependent helpers
are exercised against small temp repos where cheap, and otherwise covered
by the integration run in the workflow.
"""

from __future__ import annotations

import unittest
import unittest.mock
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT_PATH = Path(__file__).resolve().parent / "propose-grammar-update"


def _load_script_module():
    """Load scripts/propose-grammar-update as the `propose` module."""
    loader = SourceFileLoader("propose_grammar_update", str(SCRIPT_PATH))
    spec = spec_from_loader("propose_grammar_update", loader)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pg = _load_script_module()


###############################################################################
# Tag parsing and sorting #
###############################################################################


class TestStableTagFilter(unittest.TestCase):
    def test_matches_v_and_bare_semver(self):
        for tag in ("v0.25.0", "0.3.8", "v1.2.13", "2.3", "v10.0.0.1"):
            self.assertRegex(tag, pg._STABLE_TAG_RE)

    def test_rejects_prereleases_and_non_versions(self):
        for tag in ("v0.25.0-rc1", "v1.0.0-beta", "nightly",
                    "parser-1.0", "2024-01-01", "release", "v1"):
            self.assertNotRegex(tag, pg._STABLE_TAG_RE)


class TestVersionKey(unittest.TestCase):
    def test_v_prefix_stripped_and_numeric(self):
        self.assertEqual(pg.version_key("v0.25.0"), (0, 25, 0))
        self.assertEqual(pg.version_key("2.3"), (2, 3))

    def test_orders_correctly(self):
        # The classic sort -V trap: 0.25.0 must beat 0.5.0.
        tags = ["v0.5.0", "v0.25.0", "v0.9.0", "v0.10.0"]
        self.assertEqual(max(tags, key=pg.version_key), "v0.25.0")

    def test_bare_and_v_mix(self):
        self.assertEqual(max(["1.2.13", "v1.10.0"], key=pg.version_key), "v1.10.0")


###############################################################################
# URL handling #
###############################################################################


class TestUrlRewrite(unittest.TestCase):
    """gitmodules_url must rewrite SSH URLs to HTTPS for keyless ls-remote."""

    def _gitmodules_repo(self, root: Path, path: str, url: str) -> Path:
        gm = root / ".gitmodules"
        gm.write_text(
            f'[submodule "x"]\n\tpath = {path}\n\turl = {url}\n'
        )
        return root

    def test_ssh_rewritten_to_https(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rel = "lang/semgrep-grammars/src/tree-sitter-gosu"
            self._gitmodules_repo(root, rel, "git@github.com:tarides/tree-sitter-gosu.git")
            url = pg.gitmodules_url(root, root / rel)
            self.assertEqual(url, "https://github.com/tarides/tree-sitter-gosu.git")

    def test_https_passthrough(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rel = "lang/semgrep-grammars/src/tree-sitter-python"
            self._gitmodules_repo(root, rel, "https://github.com/tree-sitter/tree-sitter-python.git")
            url = pg.gitmodules_url(root, root / rel)
            self.assertEqual(url, "https://github.com/tree-sitter/tree-sitter-python.git")

    def test_matches_by_path_not_section_name(self):
        # java's section name differs from its path; we key on path.
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / ".gitmodules").write_text(
                '[submodule "lang/tree-sitter-java"]\n'
                "\tpath = lang/semgrep-grammars/src/tree-sitter-java\n"
                "\turl = https://github.com/tree-sitter/tree-sitter-java.git\n"
            )
            url = pg.gitmodules_url(
                root, root / "lang/semgrep-grammars/src/tree-sitter-java"
            )
            self.assertEqual(url, "https://github.com/tree-sitter/tree-sitter-java.git")

    def test_unknown_path_returns_none(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / ".gitmodules").write_text("")
            self.assertIsNone(
                pg.gitmodules_url(root, root / "lang/semgrep-grammars/src/tree-sitter-nope")
            )


###############################################################################
# Version-file mapping #
###############################################################################


class TestLanguageTsVersion(unittest.TestCase):
    def _repo_with_versions(self, root: Path, mapping: dict[str, list[str]]) -> None:
        lang = root / "lang"
        lang.mkdir()
        for version, names in mapping.items():
            (lang / f"languages-{version}").write_text("\n".join(names) + "\n")

    def test_finds_the_one_version(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._repo_with_versions(root, {
                "0.20.6": ["java", "ruby"],
                "0.26.3": ["python", "php"],
            })
            self.assertEqual(pg.language_ts_version(root, "python"), "0.26.3")
            self.assertEqual(pg.language_ts_version(root, "java"), "0.20.6")

    def test_absent_returns_none(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._repo_with_versions(root, {"0.26.3": ["python"]})
            # gomod is in no languages-* file.
            self.assertIsNone(pg.language_ts_version(root, "go-mod"))


###############################################################################
# PR shaping #
###############################################################################


class TestPrShaping(unittest.TestCase):
    def test_branch_name_is_tag_keyed(self):
        self.assertEqual(
            pg.branch_name("python", "v0.25.0"), "grammar-update/python/v0.25.0"
        )

    def test_compare_url_strips_dot_git(self):
        self.assertEqual(
            pg.compare_url("https://github.com/tree-sitter/tree-sitter-go.git", "abc", "v0.25.0"),
            "https://github.com/tree-sitter/tree-sitter-go/compare/abc...v0.25.0",
        )

    def test_pr_body_has_key_fields_and_footer(self):
        result = {
            "language": "python", "ts_version": "0.26.3",
            "old_sha": "old123", "new_sha": "new456", "new_tag": "v0.25.0",
            "corpus_diff": "- a\n+ b", "test_log_tail": "ok",
        }
        body = pg.pr_body(result, "https://github.com/tree-sitter/tree-sitter-python.git")
        self.assertIn("v0.25.0", body)
        self.assertIn("old123", body)
        self.assertIn(":error", body)            # review reminder present
        self.assertIn("```diff", body)            # diff rendered when present
        self.assertIn("Claude Code", body)        # required footer

    def test_pr_body_handles_empty_diff(self):
        result = {
            "language": "php", "ts_version": "0.26.3",
            "old_sha": "o", "new_sha": "n", "new_tag": "v0.24.2",
            "corpus_diff": "", "test_log_tail": "",
        }
        body = pg.pr_body(result, "https://github.com/tree-sitter/tree-sitter-php.git")
        self.assertIn("_No corpus snapshot changes._", body)


###############################################################################
# Downstream: release dialects + agent prompt #
###############################################################################


class TestReleaseDialects(unittest.TestCase):
    def test_filters_to_existing_repos(self):
        # php fans out to [php, php-only] but only semgrep-php exists.
        with unittest.mock.patch.object(
            pg, "downstream_repo_exists", lambda d: d != "php-only"
        ):
            self.assertEqual(pg.release_dialects("php", "php"), ["php"])

    def test_keeps_all_when_all_exist(self):
        with unittest.mock.patch.object(pg, "downstream_repo_exists", lambda _d: True):
            self.assertEqual(
                pg.release_dialects("typescript", "typescript"),
                ["typescript", "tsx"],
            )

    def test_falls_back_to_language_when_none_exist(self):
        with unittest.mock.patch.object(pg, "downstream_repo_exists", lambda _d: False):
            self.assertEqual(pg.release_dialects("php", "php"), ["php"])


class TestAgentPrompt(unittest.TestCase):
    def test_references_correct_proprietary_paths(self):
        p = pg.agent_prompt("php", "php", "grammar-update/php/v0.24.2", "v0.24.2")
        self.assertIn("OSS/languages/php/tree-sitter/semgrep-php", p)
        self.assertIn("Parse_php_tree_sitter.ml", p)
        self.assertIn("grammar-update/php/v0.24.2", p)
        self.assertIn("v0.24.2", p)
        self.assertIn("draft PR", p)

    def test_aliased_language_uses_wrapper_for_submodule(self):
        # apex's submodule wrapper is sfapex; the parse file stays apex.
        p = pg.agent_prompt("apex", "sfapex", "grammar-update/apex/v2.3", "v2.3")
        self.assertIn("semgrep-sfapex", p)
        self.assertIn("Parse_apex_tree_sitter.ml", p)


###############################################################################
# Misc helpers #
###############################################################################


class TestTail(unittest.TestCase):
    def test_returns_last_n_lines(self):
        text = "\n".join(str(i) for i in range(100))
        self.assertEqual(pg.tail(text, 3), "97\n98\n99")

    def test_shorter_than_n_is_whole(self):
        self.assertEqual(pg.tail("a\nb", 10), "a\nb")


if __name__ == "__main__":
    unittest.main()
