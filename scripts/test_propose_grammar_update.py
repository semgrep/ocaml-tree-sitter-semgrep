"""Unit tests for scripts/propose-grammar-update.

Mirrors scripts/test_update_grammar.py: load the extensionless driver via
SourceFileLoader, then test its pure logic (tag parsing/sorting, URL
rewrite, version mapping, PR-body shaping). Git/network-dependent helpers
are exercised against small temp repos where cheap, and otherwise covered
by the integration run in the workflow.
"""

from __future__ import annotations

import contextlib
import sys
import unittest
import unittest.mock
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

from packaging.version import Version

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
            self.assertEqual(
                pg.language_ts_version(root, pg.LangAndWrapper("python", "python")),
                "0.26.3",
            )
            self.assertEqual(
                pg.language_ts_version(root, pg.LangAndWrapper("java", "java")),
                "0.20.6",
            )

    def test_absent_returns_none(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            self._repo_with_versions(root, {"0.26.3": ["python"]})
            # gomod is in no languages-* file.
            self.assertIsNone(
                pg.language_ts_version(root, pg.LangAndWrapper("gomod", "go-mod"))
            )


###############################################################################
# PR shaping #
###############################################################################


class TestPrShaping(unittest.TestCase):
    def test_branch_name_is_tag_keyed(self):
        self.assertEqual(
            pg.branch_name(pg.LangAndWrapper("python", "python"), "v0.25.0"),
            "grammar-update/python/v0.25.0",
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
            self.assertEqual(
                pg.release_dialects(pg.LangAndWrapper("php", "php")), ["php"]
            )

    def test_keeps_all_when_all_exist(self):
        with unittest.mock.patch.object(pg, "downstream_repo_exists", lambda _d: True):
            self.assertEqual(
                pg.release_dialects(pg.LangAndWrapper("typescript", "typescript")),
                ["typescript", "tsx"],
            )

    def test_falls_back_to_language_when_none_exist(self):
        with unittest.mock.patch.object(pg, "downstream_repo_exists", lambda _d: False):
            self.assertEqual(
                pg.release_dialects(pg.LangAndWrapper("php", "php")), ["php"]
            )


class TestProposeFailurePath(unittest.TestCase):
    """Exercise propose()'s test-lang-fails branch (classify-only, keep=False).

    This is the path that previously shipped a NameError (`tag` undefined) —
    these tests fail loudly if it regresses.
    """

    TARGET = pg.Target(
        lang=pg.LangAndWrapper(language="php", wrapper="php"), submodule=Path("/tmp/sub"),
        ts_version="0.26.3", url="https://x/y.git", tag="v0.24.2",
    )

    def _run(self, test_returncodes, review_agent=True, bump_rc=0,
             shas=("OLD", "NEW")):
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
            run_update_grammar=lambda *a, **k: sp.CompletedProcess(
                [], bump_rc, "bump-log", ""),
            submodule_head=unittest.mock.Mock(side_effect=list(shas)),
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

    def test_failed_bump_without_move_is_failed_not_noop(self):
        # update-grammar dies before moving the submodule -> must surface
        # as failed (previously misclassified as no-op).
        r, _agent = self._run([], bump_rc=1, shas=("OLD", "OLD"))
        self.assertEqual(r.status, pg.STATUS_FAILED)
        self.assertEqual(r.detail, "update-grammar failed")
        self.assertIn("bump-log", r.test_log_tail)

    def test_clean_noop_still_noop(self):
        r, _agent = self._run([], bump_rc=0, shas=("OLD", "OLD"))
        self.assertEqual(r.status, pg.STATUS_NO_OP)

    def test_failed_bump_with_move_proceeds_to_test_lang(self):
        # Non-zero bump but the submodule moved: expected (its internal
        # test-lang fails on stale snapshots) — our re-test decides.
        r, _agent = self._run([0], bump_rc=1)
        self.assertEqual(r.status, pg.STATUS_UPDATED)


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

    LANG = pg.LangAndWrapper(language="php", wrapper="php")

    def _patch(self, recorded, tag_sha, tag="v1.0.0", url="https://x/y.git"):
        # is_up_to_date compares recorded gitlink SHA vs the tag's commit SHA.
        return (
            unittest.mock.patch.object(
                pg, "resolve_target",
                lambda root, lang, tree_sitter_versions=None, deep=True: pg.Target(
                    lang=lang, submodule=Path("/tmp/sub"),
                    ts_version="0.26.3", url=url, tag=tag,
                ),
            ),
            unittest.mock.patch.object(pg, "recorded_submodule_sha", lambda r, s: recorded),
            unittest.mock.patch.object(pg, "tag_commit_sha", lambda u, t: tag_sha),
        )

    def test_up_to_date_when_shas_match(self):
        p1, p2, p3 = self._patch(recorded="abc123", tag_sha="abc123")
        with p1, p2, p3:
            self.assertIs(pg.is_up_to_date(Path("."), self.LANG), True)

    def test_behind_when_shas_differ(self):
        p1, p2, p3 = self._patch(recorded="abc123", tag_sha="def456")
        with p1, p2, p3:
            self.assertIs(pg.is_up_to_date(Path("."), self.LANG), False)

    def test_none_when_no_tag(self):
        with unittest.mock.patch.object(
            pg, "resolve_target",
            lambda root, lang, tree_sitter_versions=None, deep=True: pg.Target(
                lang=lang, submodule=Path("/tmp/s"),
                url="u", tag=None,
            ),
        ):
            self.assertIsNone(pg.is_up_to_date(Path("."), self.LANG))


class TestReviewAgent(unittest.TestCase):
    def test_prompt_drives_fix_semgrep_grammar_skill(self):
        p = pg.review_agent_prompt(
            pg.LangAndWrapper("php", "php"), "v0.24.2", "FAIL log here"
        )
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


class TestTagCommitSha(unittest.TestCase):
    """Annotated tags must resolve to the PEELED commit, not the tag object.

    ls-remote sorts by refname, so the plain (tag-object) line comes first;
    grabbing it made every annotated-tag language look permanently behind.
    """

    def _with_ls_remote(self, stdout):
        import subprocess as sp
        return unittest.mock.patch.object(
            pg, "git_query",
            lambda cmd, cwd: sp.CompletedProcess(cmd, 0, stdout, ""),
        )

    def test_annotated_tag_prefers_peeled_sha(self):
        out = ("tagobj111\trefs/tags/v1.0.0\n"
               "commit222\trefs/tags/v1.0.0^{}\n")
        with self._with_ls_remote(out):
            self.assertEqual(pg.tag_commit_sha("u", "v1.0.0"), "commit222")

    def test_lightweight_tag_falls_back_to_plain(self):
        with self._with_ls_remote("commit333\trefs/tags/v1.0.0\n"):
            self.assertEqual(pg.tag_commit_sha("u", "v1.0.0"), "commit333")

    def test_no_output_returns_none(self):
        with self._with_ls_remote(""):
            self.assertIsNone(pg.tag_commit_sha("u", "v1.0.0"))


class TestExistingProposal(unittest.TestCase):
    """The cheap pre-build check for an already-proposed lang+tag."""

    TARGET = pg.Target(pg.LangAndWrapper(language="php", wrapper="php"), submodule=Path("/tmp/s"),
                       ts_version="0.26.3", tag="v0.24.2")

    def test_existing_branch_short_circuits(self):
        with unittest.mock.patch.object(pg, "proposal_exists", lambda r, b: True):
            r = pg.existing_proposal(Path("."), self.TARGET)
        self.assertEqual(r.status, pg.STATUS_EXISTS)
        self.assertEqual(r.branch, "grammar-update/php/v0.24.2")

    def test_absent_branch_returns_none(self):
        with unittest.mock.patch.object(pg, "proposal_exists", lambda r, b: False):
            self.assertIsNone(pg.existing_proposal(Path("."), self.TARGET))

    def test_no_tag_returns_none(self):
        import dataclasses
        target = dataclasses.replace(self.TARGET, tag=None)
        self.assertIsNone(pg.existing_proposal(Path("."), target))


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


###############################################################################
# Smart tag+version resolution #
###############################################################################


class TestListStableTags(unittest.TestCase):
    def test_sorted_newest_first(self):
        import subprocess as sp
        out = "a\trefs/tags/v0.20.0\nb\trefs/tags/v0.25.0\nc\trefs/tags/v0.9.0\n"
        with unittest.mock.patch.object(
            pg, "git_query", lambda cmd, cwd: sp.CompletedProcess(cmd, 0, out, "")
        ):
            self.assertEqual(pg._list_stable_tags("u"), ["v0.25.0", "v0.20.0", "v0.9.0"])

    def test_passes_patterns_to_ls_remote(self):
        import subprocess as sp
        seen = []

        def capture(cmd, cwd):
            seen.append(cmd)
            return sp.CompletedProcess(cmd, 0, "", "")

        with unittest.mock.patch.object(pg, "git_query", capture):
            pg._list_stable_tags("u")
        self.assertEqual(seen[0][:4], ["git", "ls-remote", "--tags", "--refs"])
        self.assertIn("refs/tags/v[0-9]*", seen[0])
        self.assertIn("refs/tags/[0-9]*", seen[0])

    def test_empty_on_failure(self):
        import subprocess as sp
        with unittest.mock.patch.object(
            pg, "git_query", lambda cmd, cwd: sp.CompletedProcess(cmd, 1, "", "")
        ):
            self.assertEqual(pg._list_stable_tags("u"), [])

    def test_latest_stable_tag_still_works(self):
        with unittest.mock.patch.object(
            pg, "_list_stable_tags", lambda url: ["v0.25.0", "v0.20.0"]
        ):
            self.assertEqual(pg.latest_stable_tag("u"), "v0.25.0")
        with unittest.mock.patch.object(pg, "_list_stable_tags", lambda url: []):
            self.assertIsNone(pg.latest_stable_tag("u"))

    def test_list_newer_stable_tags_filters_and_stops(self):
        fetched = pg.FetchedSubmodule(Path("/tmp/s"))
        with unittest.mock.patch.object(
            pg, "_list_stable_tags",
            lambda url: ["v0.25.0", "v0.24.0", "v0.20.0"],
        ), unittest.mock.patch.object(
            pg.FetchedSubmodule, "is_newer_than",
            lambda self, tag, old_sha: tag not in ("v0.24.0", "v0.20.0"),
        ):
            result = fetched.list_newer_stable_tags("u", "OLD")
            self.assertIsInstance(result, pg.NewerStableTags)
            self.assertEqual(result.tags, ["v0.25.0"])

    def test_list_newer_stable_tags_no_stable_tags(self):
        fetched = pg.FetchedSubmodule(Path("/tmp/s"))
        with unittest.mock.patch.object(pg, "_list_stable_tags", lambda url: []):
            self.assertIsInstance(
                fetched.list_newer_stable_tags("u", "OLD"), pg.NoStableTags,
            )


class TestPickTsVersion(unittest.TestCase):
    VERSIONS = [Version("0.26.3"), Version("0.22.6"), Version("0.20.8")]

    def test_no_constraints_picks_newest(self):
        self.assertEqual(
            pg._pick_ts_version(self.VERSIONS, floor=None, ceiling=None),
            Version("0.26.3"),
        )

    def test_cpp_caps_below_0_24(self):
        self.assertEqual(
            pg._pick_ts_version(
                self.VERSIONS, floor=None, ceiling=pg._CPP_SCANNER_CEILING,
            ),
            Version("0.22.6"),
        )

    def test_floor_filters_low_versions(self):
        self.assertEqual(
            pg._pick_ts_version(
                self.VERSIONS, floor=Version("0.22.0"), ceiling=None,
            ),
            Version("0.26.3"),
        )

    def test_pick_none_when_floor_conflicts_with_cpp(self):
        # Picker itself does not relax; _evaluate_tag clears the floor for
        # the semgrep-only-C++ case before calling.
        self.assertIsNone(pg._pick_ts_version(
            self.VERSIONS,
            floor=Version("0.24.4"),
            ceiling=pg._CPP_SCANNER_CEILING,
        ))

    def test_pick_none_when_unmet_floor(self):
        self.assertIsNone(
            pg._pick_ts_version(
                self.VERSIONS, floor=Version("0.30.0"), ceiling=None,
            )
        )


class TestVersionNote(unittest.TestCase):
    LANG = pg.LangAndWrapper(language="ruby", wrapper="ruby")

    def test_none_without_cpp(self):
        self.assertIsNone(pg._version_note(
            self.LANG, "v1", Version("0.26.3"),
            upstream_cpp=False, semgrep_cpp=False,
            floor=None,
        ))

    def test_semgrep_only_cpp(self):
        note = pg._version_note(
            self.LANG, "v1", Version("0.22.6"),
            upstream_cpp=False, semgrep_cpp=True,
            floor=None,
        )
        self.assertIn("semgrep-ruby/src/scanner.cc", note)
        self.assertIn("still C++", note)

    def test_floor_conflict_appended_when_chosen_below_floor(self):
        note = pg._version_note(
            self.LANG, "v1", Version("0.22.6"),
            upstream_cpp=False, semgrep_cpp=True,
            floor=Version("0.24.4"),
        )
        self.assertIn("0.24.4", note)
        self.assertIn("conflicts", note)

    def test_compatible_floor_not_mentioned(self):
        note = pg._version_note(
            self.LANG, "v1", Version("0.22.6"),
            upstream_cpp=False, semgrep_cpp=True,
            floor=Version("0.20.0"),
        )
        self.assertNotIn("conflicts", note)
        self.assertNotIn("0.20.0", note)


class TestRequiresAbi15(unittest.TestCase):
    def _fetched(self):
        return pg.FetchedSubmodule(Path("/tmp/s"))

    def test_detects_top_level_reserved_field(self):
        text = 'module.exports = grammar({\n  name: "x",\n  reserved: {\n    global: $ => [],\n  },\n});\n'
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: text
        ):
            self.assertTrue(pg._requires_abi15(self._fetched(), "v1.0.0"))

    def test_false_when_absent(self):
        text = 'module.exports = grammar({\n  name: "x",\n  rules: {},\n});\n'
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: text
        ):
            self.assertFalse(pg._requires_abi15(self._fetched(), "v1.0.0"))

    def test_false_when_file_absent(self):
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: None
        ):
            self.assertFalse(pg._requires_abi15(self._fetched(), "v1.0.0"))


class TestDeclaredMinTsVersion(unittest.TestCase):
    def _fetched(self):
        return pg.FetchedSubmodule(Path("/tmp/s"))

    def test_extracts_from_dev_dependencies(self):
        text = '{"devDependencies": {"tree-sitter-cli": "^0.25.3"}}'
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: text
        ):
            self.assertEqual(pg._declared_min_ts_version(self._fetched(), "v1"), "0.25.3")

    def test_extracts_from_peer_dependencies(self):
        text = '{"peerDependencies": {"tree-sitter-cli": "~0.24.0"}}'
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: text
        ):
            self.assertEqual(pg._declared_min_ts_version(self._fetched(), "v1"), "0.24.0")

    def test_none_when_absent(self):
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: '{"name": "x"}'
        ):
            self.assertIsNone(pg._declared_min_ts_version(self._fetched(), "v1"))

    def test_none_when_file_missing(self):
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: None
        ):
            self.assertIsNone(pg._declared_min_ts_version(self._fetched(), "v1"))

    def test_none_on_invalid_json(self):
        with unittest.mock.patch.object(
            pg.FetchedSubmodule, "read_tag_file", lambda self, t, p: "not json"
        ):
            self.assertIsNone(pg._declared_min_ts_version(self._fetched(), "v1"))


class TestResolveTagAndVersion(unittest.TestCase):
    """Orchestration tests: mock every git-touching helper, verify the
    newer-than-current / tag-walk-back / version-capping / floor logic."""

    OLD_SHA = "OLDSHA"
    LANG = pg.LangAndWrapper(language="ruby", wrapper="ruby")
    VERSIONS = [Version("0.26.3"), Version("0.22.6"), Version("0.20.8")]  # newest-first, as main() sorts

    @contextlib.contextmanager
    def _patch(self, tags, reserved_tags=(), cpp_scanner_tags=(), floors=None,
              fetch_ok=True, semgrep_cpp=False):
        floors = floors or {}

        def fake_fetch(submodule):
            if not fetch_ok:
                return None
            fetched = unittest.mock.MagicMock(spec=pg.FetchedSubmodule)
            fetched.path = submodule

            def list_newer(url, old_sha):
                if tags is None:
                    return pg.NoStableTags()
                return pg.NewerStableTags(list(tags))

            fetched.list_newer_stable_tags.side_effect = list_newer
            return fetched

        with unittest.mock.patch.multiple(
            pg,
            _requires_abi15=lambda sub, tag: tag in reserved_tags,
            _upstream_has_cpp_scanner=lambda sub, tag: tag in cpp_scanner_tags,
            _semgrep_has_cpp_scanner=lambda root, lang: semgrep_cpp,
            _declared_min_ts_version=lambda sub, tag: floors.get(tag),
        ), unittest.mock.patch.object(pg.FetchedSubmodule, "fetch", fake_fetch):
            yield

    def _resolve(self, **kwargs):
        versions = kwargs.pop("versions", self.VERSIONS)
        with self._patch(**kwargs):
            return pg.resolve_tag_and_version(
                Path("."), Path("/tmp/s"), "u", versions, self.OLD_SHA, self.LANG,
            )

    def test_picks_latest_tag_and_highest_version(self):
        r = self._resolve(tags=["v0.26.0", "v0.25.0"])
        self.assertIsInstance(r, pg.VersionOk)
        self.assertEqual(r.tag, "v0.26.0")
        self.assertEqual(r.ts_version, "0.26.3")
        self.assertIsNone(r.note)

    def test_abi15_tag_falls_back_to_older_tag(self):
        r = self._resolve(tags=["v0.26.0", "v0.25.0"], reserved_tags=["v0.26.0"])
        self.assertIsInstance(r, pg.VersionOk)
        self.assertEqual(r.tag, "v0.25.0")

    def test_all_tags_require_abi15_is_an_error(self):
        r = self._resolve(tags=["v0.26.0", "v0.25.0"],
                          reserved_tags=["v0.26.0", "v0.25.0"])
        self.assertIsInstance(r, pg.VersionErr)
        self.assertIn("ABI 15", r.error)

    def test_cpp_scanner_caps_below_0_24(self):
        r = self._resolve(tags=["v1.0.0"], cpp_scanner_tags=["v1.0.0"])
        self.assertIsInstance(r, pg.VersionOk)
        self.assertEqual(r.ts_version, "0.22.6")
        self.assertIn("scanner.cc", r.note)
        self.assertIn("upstream", r.note)

    def test_semgrep_only_cpp_scanner_caps_and_reports(self):
        # Upstream has no scanner.cc, but semgrep-<wrapper> still does --
        # same cap, and the note must call out the stale extension fork.
        r = self._resolve(tags=["v1.0.0"], semgrep_cpp=True)
        self.assertIsInstance(r, pg.VersionOk)
        self.assertEqual(r.ts_version, "0.22.6")
        self.assertIn("semgrep-ruby/src/scanner.cc", r.note)
        self.assertIn("still C++", r.note)
        self.assertIn("upstream", r.note)

    def test_cpp_ceiling_wins_over_conflicting_floor(self):
        # Floor >= 0.24 is incompatible with a C++ scanner; keep the newest
        # tag and the < 0.24 pin, and mention the conflict.
        r = self._resolve(
            tags=["v0.23.1"], semgrep_cpp=True, floors={"v0.23.1": "0.24.4"},
        )
        self.assertIsInstance(r, pg.VersionOk)
        self.assertEqual(r.tag, "v0.23.1")
        self.assertEqual(r.ts_version, "0.22.6")
        self.assertIn("0.24.4", r.note)
        self.assertIn("conflicts", r.note)

    def test_unmet_floor_is_an_error(self):
        r = self._resolve(tags=["v1.0.0"], floors={"v1.0.0": "0.30.0"})
        self.assertIsInstance(r, pg.VersionErr)
        self.assertIn("0.30.0", r.error)

    def test_no_tags_upstream_is_an_error(self):
        r = self._resolve(tags=None)
        self.assertIsInstance(r, pg.VersionErr)
        self.assertIn("no stable release tag", r.error)

    def test_stops_at_first_tag_not_newer_than_current(self):
        # list_newer_stable_tags already filtered out v0.24.0 and older; only
        # the ABI-15 v0.25.0 remains as a candidate.
        r = self._resolve(tags=["v0.25.0"], reserved_tags=["v0.25.0"])
        self.assertIsInstance(r, pg.VersionErr)
        self.assertIn("ABI 15", r.error)

    def test_no_newer_tag_is_a_distinct_error(self):
        r = self._resolve(tags=[])
        self.assertIsInstance(r, pg.VersionErr)
        self.assertIn("already at", r.error)

    def test_examines_at_most_max_tags(self):
        many_tags = [f"v0.{i}.0" for i in range(30, 0, -1)]  # 30 tags, all bad
        examined = []

        def counting_abi15(sub, tag):
            examined.append(tag)
            return True

        with self._patch(tags=many_tags, reserved_tags=many_tags), \
             unittest.mock.patch.object(pg, "_requires_abi15", counting_abi15):
            r = pg.resolve_tag_and_version(
                Path("."), Path("/tmp/s"), "u", self.VERSIONS, self.OLD_SHA, self.LANG,
            )
        self.assertEqual(len(examined), pg.MAX_TAGS_EXAMINED)
        self.assertEqual(examined, many_tags[: pg.MAX_TAGS_EXAMINED])
        self.assertIsInstance(r, pg.VersionErr)


class TestFetchTagsPreservesAncestry(unittest.TestCase):
    """Regression test with a REAL git repo (no mocks): FetchedSubmodule.fetch
    must not re-shallow the submodule, or is_newer_than's merge-base check
    silently breaks for any tag more than one commit past old_sha -- i.e.
    almost every real bump. A mocked test can't catch this class of bug."""

    def _git(self, cwd, *args):
        import subprocess
        return subprocess.run(["git", *args], cwd=cwd, check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_ancestry_survives_fetch_tags_after_unshallow(self):
        import subprocess
        with TemporaryDirectory() as d:
            root = Path(d)
            upstream = root / "upstream"
            upstream.mkdir()
            self._git(upstream, "init", "-q")
            self._git(upstream, "config", "user.email", "t@t.com")
            self._git(upstream, "config", "user.name", "t")
            old_sha = None
            for i in range(3):
                (upstream / "f.txt").write_text(str(i))
                self._git(upstream, "add", "-A")
                self._git(upstream, "commit", "-q", "-m", f"c{i}")
                self._git(upstream, "tag", f"v1.{i}.0")
                if i == 0:
                    old_sha = self._git(upstream, "rev-parse", "HEAD")

            submodule = root / "sub"
            # --no-local: a plain local-path clone silently ignores --depth
            # (git hardlinks the whole object store), so this is needed to
            # get a genuinely shallow clone -- matching what CI's network
            # clone of the real submodule produces.
            subprocess.run(
                ["git", "clone", "-q", "--no-local", "--depth", "1", "--branch", "v1.0.0",
                 str(upstream), str(submodule)],
                check=True, capture_output=True,
            )
            self.assertTrue(pg.ug.is_shallow_repo(submodule))
            subprocess.run(["git", "fetch", "-q", "origin", "--unshallow"],
                           cwd=submodule, check=True, capture_output=True)

            fetched = pg.FetchedSubmodule.fetch(submodule)
            self.assertIsNotNone(fetched)
            self.assertTrue(
                fetched.is_newer_than("v1.2.0", old_sha),
                "merge-base ancestry check failed -- FetchedSubmodule.fetch "
                "likely re-shallowed the submodule",
            )


class TestResolveTargetDeepFlag(unittest.TestCase):
    def test_is_up_to_date_uses_shallow_resolution(self):
        calls = []
        lang = pg.LangAndWrapper(language="php", wrapper="php")

        def fake_resolve(root, lang, tree_sitter_versions=None, deep=True):
            calls.append(deep)
            return pg.Target(
                lang=lang, submodule=Path("/tmp/s"),
                ts_version="0.26.3", url="u", tag="v1.0.0",
            )
        with unittest.mock.patch.object(pg, "resolve_target", fake_resolve), \
             unittest.mock.patch.object(pg, "recorded_submodule_sha", lambda r, s: "x"), \
             unittest.mock.patch.object(pg, "tag_commit_sha", lambda u, t: "x"):
            pg.is_up_to_date(Path("."), lang)
        self.assertEqual(calls, [False])


if __name__ == "__main__":
    unittest.main()
