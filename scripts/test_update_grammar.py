"""Unit tests for scripts/update-grammar.

The script has no `.py` extension, so we load it explicitly with
`SourceFileLoader`. Pure / filesystem helpers are tested directly;
git-driven helpers are tested with `unittest.mock` patching of the
module's `run` and `capture` functions.

Run with: `python -m unittest scripts/test_update_grammar.py`
"""

from __future__ import annotations

import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parent / "update-grammar"


def _load_script_module():
    """Load scripts/update-grammar as the `update_grammar` module."""
    loader = SourceFileLoader("update_grammar", str(SCRIPT_PATH))
    spec = spec_from_loader("update_grammar", loader)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ug = _load_script_module()


def make_repo(
    root: Path,
    *,
    semgrep_dirs: tuple[str, ...] = (),
    submodule_dirs: tuple[str, ...] = (),
) -> None:
    """Build a fake repo layout under `root`.

    `semgrep_dirs` and `submodule_dirs` are subdir names to create under
    `lang/semgrep-grammars/src/` (e.g., `semgrep-python`, `tree-sitter-go-mod`).
    """
    sg = root / "lang" / "semgrep-grammars" / "src"
    sg.mkdir(parents=True, exist_ok=True)
    for d in (*semgrep_dirs, *submodule_dirs):
        (sg / d).mkdir()


class TestBase(unittest.TestCase):
    """Base class that silences stdout/stderr during each test.

    The script under test prints progress/log lines as part of normal
    operation; capturing keeps successful test runs clean.
    """

    def setUp(self) -> None:
        super().setUp()
        for ctx in (redirect_stdout(StringIO()), redirect_stderr(StringIO())):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)


class FilesystemTest(TestBase):
    """Base class providing a per-test temporary directory at `self.root`."""

    def setUp(self) -> None:
        super().setUp()
        tmpdir = TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.root = Path(tmpdir.name)


# ----- Pure / filesystem helpers -------------------------------------------


class LanguageCandidatesTests(TestBase):
    def test_no_alias_returns_singleton(self):
        self.assertEqual(ug.language_candidates("python"), ["python"])

    def test_alias_appended_in_order(self):
        # SUBMODULE_ALIASES: gomod -> go-mod
        self.assertEqual(ug.language_candidates("gomod"), ["gomod", "go-mod"])

    def test_alias_target_passed_directly_is_singleton(self):
        # "go-mod" has no alias entry; result deduplicates to one element.
        self.assertEqual(ug.language_candidates("go-mod"), ["go-mod"])


class LanguagesEntriesTests(FilesystemTest):
    def test_write_then_read_roundtrip(self):
        path = self.root / "languages-0.22.6"
        ug.write_sorted_languages_entries(path, {"python", "ruby", "go"})
        self.assertEqual(path.read_text(), "go\npython\nruby\n")
        self.assertEqual(
            ug.read_languages_entries(path), {"python", "ruby", "go"}
        )

    def test_read_skips_blank_and_whitespace_only_lines(self):
        path = self.root / "languages-0.22.6"
        path.write_text("python\n\n  \nruby\n")
        self.assertEqual(
            ug.read_languages_entries(path), {"python", "ruby"}
        )

    def test_read_strips_surrounding_whitespace(self):
        path = self.root / "languages-0.22.6"
        path.write_text("python \n  ruby\n\tgo\t\n")
        self.assertEqual(
            ug.read_languages_entries(path), {"python", "ruby", "go"}
        )


class DiscoverVersionFilesTests(FilesystemTest):
    def setUp(self) -> None:
        super().setUp()
        self.lang = self.root / "lang"
        self.lang.mkdir()

    def test_maps_version_to_path(self):
        (self.lang / "languages-0.22.6").write_text("")
        (self.lang / "languages-0.26.3").write_text("")
        result = ug.discover_version_files(self.root, "languages")
        self.assertEqual(set(result), {"0.22.6", "0.26.3"})
        self.assertEqual(result["0.22.6"].name, "languages-0.22.6")
        self.assertEqual(result["0.26.3"].name, "languages-0.26.3")

    def test_ignores_readme_files(self):
        (self.lang / "languages-0.22.6").write_text("")
        (self.lang / "languages-0.22.6.readme").write_text("docs")
        result = ug.discover_version_files(self.root, "languages")
        self.assertEqual(set(result), {"0.22.6"})

    def test_returns_empty_when_no_matches(self):
        self.assertEqual(ug.discover_version_files(self.root, "languages"), {})

    def test_prefix_is_respected(self):
        (self.lang / "languages-0.22.6").write_text("")
        (self.lang / "language-variants-0.22.6").write_text("")
        self.assertEqual(
            set(ug.discover_version_files(self.root, "language-variants")),
            {"0.22.6"},
        )


class ResolveSubmoduleTests(FilesystemTest):
    def test_finds_canonical(self):
        make_repo(self.root, submodule_dirs=("tree-sitter-python",))
        expected = self.root / "lang" / "semgrep-grammars" / "src" / "tree-sitter-python"
        self.assertEqual(ug.resolve_submodule(self.root, "python"), expected)

    def test_finds_via_alias(self):
        make_repo(self.root, submodule_dirs=("tree-sitter-go-mod",))
        expected = self.root / "lang" / "semgrep-grammars" / "src" / "tree-sitter-go-mod"
        self.assertEqual(ug.resolve_submodule(self.root, "gomod"), expected)

    def test_finds_alias_name_passed_directly(self):
        # Passing "go-mod" (the alias target) directly should also resolve,
        # since `language_candidates` deduplicates to just ["go-mod"].
        make_repo(self.root, submodule_dirs=("tree-sitter-go-mod",))
        expected = self.root / "lang" / "semgrep-grammars" / "src" / "tree-sitter-go-mod"
        self.assertEqual(ug.resolve_submodule(self.root, "go-mod"), expected)

    def test_prefers_canonical_over_alias_when_both_exist(self):
        make_repo(
            self.root,
            submodule_dirs=("tree-sitter-gomod", "tree-sitter-go-mod"),
        )
        expected = self.root / "lang" / "semgrep-grammars" / "src" / "tree-sitter-gomod"
        self.assertEqual(ug.resolve_submodule(self.root, "gomod"), expected)

    def test_dies_when_neither_exists(self):
        make_repo(self.root)
        with self.assertRaises(SystemExit) as cm:
            ug.resolve_submodule(self.root, "nonexistent")
        self.assertEqual(cm.exception.code, 1)


class SyncMembershipTests(FilesystemTest):
    def _make_version_file(self, version: str, contents: str = "") -> Path:
        """Create `languages-<version>` under `self.root` and return its path."""
        path = self.root / f"languages-{version}"
        path.write_text(contents)
        return path

    def test_adds_to_expected_file(self):
        v1 = self._make_version_file("0.22.6", "ruby\n")
        v2 = self._make_version_file("0.26.3", "go\n")
        ug.sync_membership(
            ["python"], "0.22.6",
            {"0.22.6": v1, "0.26.3": v2}, self.root,
        )
        self.assertEqual(ug.read_languages_entries(v1), {"ruby", "python"})
        self.assertEqual(ug.read_languages_entries(v2), {"go"})

    def test_removes_from_other_version_files(self):
        v1 = self._make_version_file("0.22.6", "python\nruby\n")
        v2 = self._make_version_file("0.26.3", "go\n")
        ug.sync_membership(
            ["python"], "0.26.3",
            {"0.22.6": v1, "0.26.3": v2}, self.root,
        )
        self.assertEqual(ug.read_languages_entries(v1), {"ruby"})
        self.assertEqual(ug.read_languages_entries(v2), {"go", "python"})

    def test_idempotent_when_already_correct(self):
        v1 = self._make_version_file("0.22.6", "python\nruby\n")
        ug.sync_membership(["python"], "0.22.6", {"0.22.6": v1}, self.root)
        self.assertEqual(ug.read_languages_entries(v1), {"python", "ruby"})

    def test_handles_multiple_names(self):
        v1 = self._make_version_file("0.22.6")
        ug.sync_membership(
            ["python", "ruby"], "0.22.6", {"0.22.6": v1}, self.root,
        )
        self.assertEqual(ug.read_languages_entries(v1), {"python", "ruby"})


class CheckLanguagesMembershipTests(FilesystemTest):
    def _setup_files(
        self, semgrep_dirs: tuple[str, ...] = (),
    ) -> tuple[Path, Path]:
        """Build the repo skeleton and empty `languages-` / `language-variants-` files.

        Returns `(languages_path, language_variants_path)`.
        """
        make_repo(self.root, semgrep_dirs=semgrep_dirs)
        langs = self.root / "languages-0.22.6"
        variants = self.root / "language-variants-0.22.6"
        langs.write_text("")
        variants.write_text("")
        return langs, variants

    def test_typescript_expands_to_variants(self):
        langs, variants = self._setup_files(semgrep_dirs=("semgrep-typescript",))
        ug.check_languages_membership(
            self.root, "typescript", "0.22.6",
            {"0.22.6": langs}, {"0.22.6": variants},
        )
        langs_entries = ug.read_languages_entries(langs)
        variants_entries = ug.read_languages_entries(variants)
        self.assertEqual(langs_entries, {"typescript"})
        self.assertEqual(variants_entries, {"typescript", "tsx"})

    def test_default_lang_appears_in_both_unchanged(self):
        langs, variants = self._setup_files(semgrep_dirs=("semgrep-python",))
        ug.check_languages_membership(
            self.root, "python", "0.22.6",
            {"0.22.6": langs}, {"0.22.6": variants},
        )
        langs_entries = ug.read_languages_entries(langs)
        variants_entries = ug.read_languages_entries(variants)
        self.assertEqual(langs_entries, {"python"})
        self.assertEqual(variants_entries, {"python"})

    def test_alias_resolution_when_semgrep_dir_exists(self):
        # With a semgrep-sfapex dir present, the alias is selected as the
        # name to record, which expands to ["apex"] in LANGUAGE_VARIANTS.
        langs, variants = self._setup_files(semgrep_dirs=("semgrep-sfapex",))
        ug.check_languages_membership(
            self.root, "apex", "0.22.6",
            {"0.22.6": langs}, {"0.22.6": variants},
        )
        langs_entries = ug.read_languages_entries(langs)
        variants_entries = ug.read_languages_entries(variants)
        self.assertEqual(langs_entries, {"sfapex"})
        self.assertEqual(variants_entries, {"apex"})

    def test_dies_when_no_semgrep_dir_exists(self):
        langs, variants = self._setup_files()
        with self.assertRaises(SystemExit) as cm:
            ug.check_languages_membership(
                self.root, "python", "0.22.6",
                {"0.22.6": langs}, {"0.22.6": variants},
            )
        self.assertEqual(cm.exception.code, 1)


class RemoveStaleParsersTests(FilesystemTest):
    def _make_parser(self, *parts: str) -> Path:
        """Create a placeholder `parser.c` at `self.root/<parts>` and return its path."""
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// stale")
        return path

    def test_removes_existing_parsers(self):
        outer = self._make_parser("lang", "python", "src", "parser.c")
        inner = self._make_parser(
            "lang", "semgrep-grammars", "src", "semgrep-python", "src",
            "parser.c",
        )
        ug.remove_stale_parsers(self.root, "python")
        self.assertFalse(outer.exists())
        self.assertFalse(inner.exists())

    def test_silent_when_targets_missing(self):
        # No parser files exist; function should not raise.
        ug.remove_stale_parsers(self.root, "python")

    def test_handles_aliased_language(self):
        # gomod's submodule lives under semgrep-go-mod (alias path).
        outer = self._make_parser("lang", "gomod", "src", "parser.c")
        alias_inner = self._make_parser(
            "lang", "semgrep-grammars", "src", "semgrep-go-mod", "src",
            "parser.c",
        )
        ug.remove_stale_parsers(self.root, "gomod")
        self.assertFalse(outer.exists())
        self.assertFalse(alias_inner.exists())


# ----- argparse ------------------------------------------------------------


class ParseArgsTests(TestBase):
    CHOICES = ("0.22.6", "0.26.3")

    def test_valid_minimum_invocation(self):
        args = ug.parse_args(
            self.CHOICES,
            ["python", "0.22.6", "--ref", "abc123"],
        )
        self.assertEqual(args.language, "python")
        self.assertEqual(args.tree_sitter_version, "0.22.6")
        self.assertEqual(args.ref, "abc123")
        self.assertTrue(args.fetch)
        self.assertFalse(args.skip_release)

    def test_skip_release_flag(self):
        args = ug.parse_args(
            self.CHOICES,
            ["python", "0.22.6", "--ref", "abc", "--skip-release"],
        )
        self.assertTrue(args.skip_release)

    def test_no_fetch_flag(self):
        args = ug.parse_args(
            self.CHOICES,
            ["python", "0.22.6", "--ref", "abc", "--no-fetch"],
        )
        self.assertFalse(args.fetch)

    def test_missing_ref_is_rejected(self):
        with self.assertRaises(SystemExit) as cm:
            ug.parse_args(self.CHOICES, ["python", "0.22.6"])
        # argparse uses exit code 2 for usage errors.
        self.assertEqual(cm.exception.code, 2)

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(SystemExit) as cm:
            ug.parse_args(
                self.CHOICES,
                ["python", "9.9.9", "--ref", "abc"],
            )
        self.assertEqual(cm.exception.code, 2)


# ----- Git-driven helpers (mock-based) -------------------------------------


class GitMockTest(TestBase):
    """Base class that patches the script's `run` and `capture` symbols."""

    def setUp(self) -> None:
        super().setUp()
        run_patcher = patch.object(ug, "run")
        capture_patcher = patch.object(ug, "capture")
        self.run = run_patcher.start()
        self.capture = capture_patcher.start()
        self.addCleanup(run_patcher.stop)
        self.addCleanup(capture_patcher.stop)
        self.run.return_value = 0
        self.capture.return_value = ""


class EnsureOnBranchTests(GitMockTest):
    REPO = Path("/repo")

    def test_with_at_force_aligns_branch(self):
        ug.ensure_on_branch(self.REPO, "my-branch", at="abc123")
        self.run.assert_called_once_with(
            ["git", "checkout", "-B", "my-branch", "abc123"], cwd=self.REPO,
        )
        self.capture.assert_not_called()

    def test_no_op_when_already_on_branch(self):
        self.capture.return_value = "my-branch"
        ug.ensure_on_branch(self.REPO, "my-branch")
        self.run.assert_not_called()

    def test_creates_branch_when_missing(self):
        self.capture.return_value = "main"
        # show-ref returns 1 (not found), then checkout -b returns 0.
        self.run.side_effect = [1, 0]
        ug.ensure_on_branch(self.REPO, "new-branch")
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][:2], ["git", "show-ref"])
        self.assertEqual(commands[1], ["git", "checkout", "-b", "new-branch"])

    def test_switches_to_existing_branch(self):
        self.capture.return_value = "main"
        self.run.side_effect = [0, 0]  # show-ref says exists; checkout succeeds.
        ug.ensure_on_branch(self.REPO, "existing-branch")
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(commands[1], ["git", "checkout", "existing-branch"])


class CommitChangesTests(GitMockTest):
    ROOT = Path("/repo")

    def test_commits_when_diff_reports_changes(self):
        # `git diff --cached --quiet` returns 1 when staged changes exist.
        self.run.side_effect = [0, 1, 0]  # add, diff, commit
        ug.commit_changes(self.ROOT, "python", "old12345", "new12345")
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(commands[0], ["git", "add", "-A"])
        self.assertEqual(commands[1][:2], ["git", "diff"])
        self.assertEqual(
            commands[2],
            ["git", "commit", "-m",
             "Update tree-sitter-python grammar from old12345 to new12345"],
        )

    def test_skips_commit_when_diff_reports_clean(self):
        self.run.side_effect = [0, 0]  # add succeeds, diff reports no changes
        ug.commit_changes(self.ROOT, "python", "old12345", "new12345")
        # Only `git add` and `git diff` should have been invoked; a third
        # call would be the commit we're asserting did not happen.
        self.assertEqual(self.run.call_count, 2)


class RequireCleanWorktreeTests(GitMockTest):
    REPO = Path("/repo")

    def test_returns_when_status_empty(self):
        self.capture.return_value = ""
        # Should not raise.
        ug.require_clean_worktree(self.REPO)
        self.capture.assert_called_once_with(
            ["git", "status", "--porcelain"], cwd=self.REPO,
        )

    def test_dies_when_status_nonempty(self):
        self.capture.return_value = " M scripts/update-grammar"
        with self.assertRaises(SystemExit) as cm:
            ug.require_clean_worktree(self.REPO)
        self.assertEqual(cm.exception.code, 1)


class UpdateSubmoduleTests(GitMockTest):
    def setUp(self) -> None:
        super().setUp()
        self.root = Path("/repo")
        self.submodule = self.root / "lang" / "semgrep-grammars" / "src" / "tree-sitter-python"

    def test_returns_old_and_new_sha(self):
        self.capture.side_effect = ["old" * 14, "new" * 14]  # HEAD, then ref
        old, new = ug.update_submodule(
            self.submodule, self.root, ref="v1.0", fetch=False,
        )
        self.assertEqual(old, "old" * 14)
        self.assertEqual(new, "new" * 14)

    def test_checkout_and_stage_when_sha_changes(self):
        self.capture.side_effect = ["old_sha", "new_sha"]
        ug.update_submodule(
            self.submodule, self.root, ref="v1.0", fetch=False,
        )
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertIn(["git", "checkout", "new_sha"], commands)
        # The gitlink is staged with `--` to disambiguate the path.
        self.assertTrue(any(
            c[:3] == ["git", "add", "--"] for c in commands
        ))

    def test_no_checkout_when_sha_unchanged(self):
        # With fetch=False and the same SHA on both sides, the early-return
        # path should fire and neither checkout nor add should run.
        self.capture.side_effect = ["same_sha", "same_sha"]
        ug.update_submodule(
            self.submodule, self.root, ref="v1.0", fetch=False,
        )
        self.run.assert_not_called()

    def test_fetch_runs_when_requested(self):
        self.capture.side_effect = ["s", "s"]
        ug.update_submodule(self.submodule, self.root, ref="v1.0", fetch=True)
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertIn(["git", "fetch", "--tags", "origin"], commands)

    def test_fetch_skipped_when_disabled(self):
        self.capture.side_effect = ["s", "s"]
        ug.update_submodule(self.submodule, self.root, ref="v1.0", fetch=False)
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertNotIn(["git", "fetch", "--tags", "origin"], commands)


# ----- Misc ----------------------------------------------------------------


class RepoRootTests(TestBase):
    def test_returns_script_grandparent(self):
        # update-grammar lives at <repo>/scripts/update-grammar; grandparent
        # is the repo root.
        self.assertEqual(ug.repo_root(), SCRIPT_PATH.parent.parent)


class DieTests(TestBase):
    def test_exits_with_status_one(self):
        with self.assertRaises(SystemExit) as cm:
            ug.die("boom")
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
