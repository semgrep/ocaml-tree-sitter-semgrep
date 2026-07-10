"""Unit tests for scripts/propose-grammar-update.

Mirrors scripts/test_update_grammar.py: load the extensionless driver via
SourceFileLoader, then test its pure logic (tag parsing/sorting, URL
rewrite, version mapping, PR-body shaping). Git/network-dependent helpers
are exercised against small temp repos where cheap, and otherwise covered
by the integration run in the workflow.
"""

from __future__ import annotations

import sys
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
    # @dataclass resolves field types via sys.modules[cls.__module__], so the
    # module must be registered BEFORE exec runs the class definitions.
    sys.modules["propose_grammar_update"] = module
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
        result = pg.Result(
            language="python", ts_version="0.26.3",
            old_sha="old123", new_sha="new456", new_tag="v0.25.0",
            corpus_diff="- a\n+ b", test_log_tail="ok",
        )
        body = pg.pr_body(result, "https://github.com/tree-sitter/tree-sitter-python.git")
        self.assertIn("v0.25.0", body)
        self.assertIn("old123", body)
        self.assertIn(":error", body)            # review reminder present
        self.assertIn("```diff", body)            # diff rendered when present
        self.assertIn("Claude Code", body)        # required footer

    def test_pr_body_handles_empty_diff(self):
        result = pg.Result(
            language="php", ts_version="0.26.3",
            old_sha="o", new_sha="n", new_tag="v0.24.2",
        )
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


class TestProposeFailurePath(unittest.TestCase):
    """Exercise propose()'s test-lang-fails branch (classify-only, keep=False).

    This is the path that previously shipped a NameError (`tag` undefined) —
    these tests fail loudly if it regresses.
    """

    TARGET = pg.Target(
        language="php", wrapper="php", submodule=Path("/tmp/sub"),
        ts_version="0.26.3", url="https://x/y.git", tag="v0.24.2",
    )

    def _run(self, test_returncodes, review_agent=True):
        """Run propose() with mocked internals; test_returncodes drives the
        test-lang result(s) in sequence (first run, then post-agent re-run).
        Returns (result, review_agent_mock)."""
        import subprocess as sp
        calls = iter(test_returncodes)

        def fake_test(_lang, _root):
            return sp.CompletedProcess([], next(calls), stdout="log", stderr="")

        agent = unittest.mock.Mock(return_value=None)
        with unittest.mock.patch.multiple(
            pg,
            run_update_grammar=lambda *a, **k: sp.CompletedProcess([], 0, "", ""),
            submodule_head=unittest.mock.Mock(side_effect=["OLD", "NEW"]),
            regenerate_snapshots=lambda *a, **k: None,
            corpus_diff=lambda *a, **k: "",
            run_test_lang=fake_test,
            run_review_agent=agent,
            reset_language_state=lambda *a, **k: None,
        ):
            result = pg.propose(Path("."), self.TARGET, keep=False,
                                review_agent=review_agent)
        return result, agent

    def test_failure_returns_failed_not_nameerror(self):
        # test-lang fails, agent runs, re-test still fails -> STATUS_FAILED,
        # and crucially NO NameError on the (formerly bare) `tag`.
        r, agent = self._run([1, 1])
        self.assertEqual(r.status, pg.STATUS_FAILED)
        self.assertFalse(r.tests_adapted)
        agent.assert_called_once()

    def test_agent_recovers_sets_tests_adapted(self):
        # test-lang fails, agent adapts, re-test passes -> updated + flag.
        r, _agent = self._run([1, 0])
        self.assertEqual(r.status, pg.STATUS_UPDATED)
        self.assertTrue(r.tests_adapted)

    def test_clean_bump_is_updated_no_agent(self):
        r, agent = self._run([0])
        self.assertEqual(r.status, pg.STATUS_UPDATED)
        self.assertFalse(r.tests_adapted)
        agent.assert_not_called()

    def test_agent_not_dispatched_unless_opted_in(self):
        # The Cursor dispatch is an explicit opt-in: with review_agent=False
        # a failing bump is reported failed and the agent is NEVER invoked.
        r, agent = self._run([1], review_agent=False)
        self.assertEqual(r.status, pg.STATUS_FAILED)
        self.assertIn("not enabled", r.detail)
        agent.assert_not_called()


class TestResultArtifact(unittest.TestCase):
    """The result-<lang>.json contract between the propose and integrate jobs.

    The integrate job releases the tag/branch read back from this artifact
    (never a live re-resolved tag), so the round-trip must preserve them.
    """

    def test_round_trip_preserves_validated_tag_and_branch(self):
        r = pg.Result(language="php", ts_version="0.26.3", new_tag="v0.24.2",
                      status="updated", branch="grammar-update/php/v0.24.2")
        with TemporaryDirectory() as d:
            path = Path(d) / "result-php.json"
            path.write_text(r.to_json())
            back = pg.Result.from_file(path)
        self.assertEqual(back.new_tag, "v0.24.2")
        self.assertEqual(back.branch, "grammar-update/php/v0.24.2")
        self.assertEqual(back.status, "updated")

    def test_to_json_drops_nones_keeps_falsy(self):
        import json
        d = json.loads(pg.Result(language="php").to_json())
        self.assertNotIn("status", d)           # None dropped
        self.assertEqual(d["tests_adapted"], False)  # real bool kept

    def test_from_file_ignores_unknown_keys(self):
        # Forward compat: an artifact written by a newer script version with
        # extra fields must still load.
        with TemporaryDirectory() as d:
            path = Path(d) / "r.json"
            path.write_text('{"language": "php", "status": "updated", "novel": 1}')
            self.assertEqual(pg.Result.from_file(path).status, "updated")


###############################################################################
# Review-and-adapt agent (on test-lang failure) #
###############################################################################


class TestUpToDateFilter(unittest.TestCase):
    """The cheap pre-filter that keeps up-to-date languages out of the build."""

    def _patch(self, recorded, tag_sha, tag="v1.0.0", url="https://x/y.git"):
        # is_up_to_date compares recorded gitlink SHA vs the tag's commit SHA.
        return (
            unittest.mock.patch.object(
                pg, "resolve_target",
                lambda root, lang: pg.Target(
                    language=lang, wrapper=lang, submodule=Path("/tmp/sub"),
                    ts_version="0.26.3", url=url, tag=tag,
                ),
            ),
            unittest.mock.patch.object(pg, "recorded_submodule_sha", lambda r, s: recorded),
            unittest.mock.patch.object(pg, "tag_commit_sha", lambda u, t: tag_sha),
        )

    def test_up_to_date_when_shas_match(self):
        p1, p2, p3 = self._patch(recorded="abc123", tag_sha="abc123")
        with p1, p2, p3:
            self.assertIs(pg.is_up_to_date(Path("."), "php"), True)

    def test_behind_when_shas_differ(self):
        p1, p2, p3 = self._patch(recorded="abc123", tag_sha="def456")
        with p1, p2, p3:
            self.assertIs(pg.is_up_to_date(Path("."), "php"), False)

    def test_none_when_no_tag(self):
        with unittest.mock.patch.object(
            pg, "resolve_target",
            lambda root, lang: pg.Target(
                language=lang, wrapper=lang, submodule=Path("/tmp/s"),
                url="u", tag=None,
            ),
        ):
            self.assertIsNone(pg.is_up_to_date(Path("."), "php"))


class TestReviewAgent(unittest.TestCase):
    def test_prompt_drives_fix_semgrep_grammar_skill(self):
        p = pg.review_agent_prompt("php", "php", "v0.24.2", "FAIL log here")
        # Must invoke Marc-André's skill (not hand-rolled fix logic), pass the
        # language/tag, forbid committing, and surface the failing log.
        self.assertIn("fix-semgrep-grammar", p)
        self.assertIn("test-lang php", p)
        self.assertIn("v0.24.2", p)
        self.assertIn("do not commit", p)
        self.assertIn("FAIL log here", p)

    def test_base_branch_default_and_override(self):
        import os
        os.environ.pop("GRAMMAR_BASE_BRANCH", None)
        self.assertEqual(pg.base_branch(), "main")
        os.environ["GRAMMAR_BASE_BRANCH"] = "develop"
        try:
            self.assertEqual(pg.base_branch(), "develop")
        finally:
            os.environ.pop("GRAMMAR_BASE_BRANCH", None)

    def test_pr_body_flags_agent_adaptation(self):
        import dataclasses
        base = pg.Result(
            language="php", ts_version="0.26.3",
            old_sha="o", new_sha="n", new_tag="v0.24.2",
            corpus_diff="- a\n+ b", test_log_tail="ok",
        )
        url = "https://github.com/tree-sitter/tree-sitter-php.git"
        self.assertNotIn("agent adapted", pg.pr_body(base, url).lower())
        adapted = dataclasses.replace(base, tests_adapted=True)
        self.assertIn("agent adapted", pg.pr_body(adapted, url).lower())


###############################################################################
# Misc helpers #
###############################################################################


class TestEnvValidation(unittest.TestCase):
    """Env-sourced values that flow into git/gh argv must be validated."""

    def _with_env(self, key, value, fn):
        import os
        old = os.environ.get(key)
        os.environ[key] = value
        try:
            return fn()
        finally:
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def test_base_branch_rejects_option_injection(self):
        with self.assertRaises(SystemExit):
            self._with_env("GRAMMAR_BASE_BRANCH", "--upload-pack=evil", pg.base_branch)

    def test_github_org_rejects_shellish_values(self):
        with self.assertRaises(SystemExit):
            self._with_env("GITHUB_ORG", "x;rm -rf /", pg.github_org)

    def test_defaults_pass(self):
        self.assertEqual(pg.github_org(), "semgrep")
        self.assertEqual(pg.base_branch(), "main")


class TestTail(unittest.TestCase):
    def test_returns_last_n_lines(self):
        text = "\n".join(str(i) for i in range(100))
        self.assertEqual(pg.tail(text, 3), "97\n98\n99")

    def test_shorter_than_n_is_whole(self):
        self.assertEqual(pg.tail("a\nb", 10), "a\nb")


if __name__ == "__main__":
    unittest.main()
