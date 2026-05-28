"""Unit tests for scripts/update-grammar.

The script has no `.py` extension, so we load it explicitly with
`SourceFileLoader` (see `_load_script_module`). Tests are organized
in three layers:

* Pure / filesystem helpers (e.g. `read_languages_entries`,
  `discover_version_files`, `discover_valid_languages`) run directly
  against temporary directories.
* Argparse plumbing is exercised by calling `parse_args` directly.
* Git-driven helpers (`ensure_on_branch`, `commit_changes`,
  `require_clean_worktree`, `update_submodule`) are run against real
  temporary git repos built by `init_git_repo`. Behavior is verified
  by post-condition state (current branch, HEAD SHA, staged paths,
  porcelain status) rather than by asserting on which subprocess
  commands were invoked.

Run with: `python -m unittest scripts/test_update_grammar.py`
"""

from __future__ import annotations

import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

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


class LanguagesEntriesTests(FilesystemTest):
    def test_write_produces_sorted_newline_terminated_lines(self):
        path = self.root / "languages-0.22.6"
        ug.write_sorted_languages_entries(path, {"python", "ruby", "go"})
        self.assertEqual(path.read_text(), "go\npython\nruby\n")

    def test_write_then_read_roundtrip(self):
        path = self.root / "languages-0.22.6"
        ug.write_sorted_languages_entries(path, {"python", "ruby", "go"})
        self.assertEqual(
            ug.read_languages_entries(path), {"python", "ruby", "go"},
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

    def test_write_leaves_no_tempfile_behind(self):
        path = self.root / "languages-0.22.6"
        ug.write_sorted_languages_entries(path, {"python", "ruby"})
        # Tempfiles are hidden (start with '.') and end in '.tmp'.
        leftovers = list(self.root.glob(".languages-0.22.6.*"))
        self.assertEqual(leftovers, [])

    def test_write_failure_preserves_existing_file(self):
        # If the rename step fails, the destination must be unchanged and
        # the tempfile cleaned up. Simulate by making the destination a
        # directory so `Path.replace` raises.
        path = self.root / "languages-0.22.6"
        path.write_text("original\n")
        blocker = self.root / "block"
        blocker.mkdir()
        # Replacing a regular file with a directory fails on POSIX/macOS.
        # We hit the same failure mode by aiming the write at the directory.
        with self.assertRaises(OSError):
            ug.write_sorted_languages_entries(blocker, {"python"})
        self.assertEqual(path.read_text(), "original\n")
        # No leftover tempfiles in the target directory.
        self.assertEqual(list(self.root.glob(".block.*")), [])


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


class DiscoverValidLanguagesTests(FilesystemTest):
    def test_direct_wrapper_with_matching_submodule(self):
        make_repo(
            self.root,
            semgrep_dirs=("semgrep-python",),
            submodule_dirs=("tree-sitter-python",),
        )
        self.assertEqual(
            ug.discover_valid_languages(self.root), {"python": "python"},
        )

    def test_alias_key_added_when_target_has_wrapper_and_submodule(self):
        # apex -> sfapex: only semgrep-sfapex and tree-sitter-sfapex exist.
        make_repo(
            self.root,
            semgrep_dirs=("semgrep-sfapex",),
            submodule_dirs=("tree-sitter-sfapex",),
        )
        self.assertEqual(
            ug.discover_valid_languages(self.root),
            {"sfapex": "sfapex", "apex": "sfapex"},
        )

    def test_wrapper_with_aliased_submodule(self):
        # gomod -> go-mod: wrapper at semgrep-gomod, submodule at tree-sitter-go-mod.
        make_repo(
            self.root,
            semgrep_dirs=("semgrep-gomod",),
            submodule_dirs=("tree-sitter-go-mod",),
        )
        # "gomod" is valid (resolves wrapper directly; submodule via alias).
        # "go-mod" is NOT valid (no semgrep-go-mod wrapper).
        self.assertEqual(
            ug.discover_valid_languages(self.root), {"gomod": "gomod"},
        )

    def test_wrapper_without_matching_submodule_excluded(self):
        # Defensive: a stray semgrep-foo without tree-sitter-foo is not valid.
        make_repo(self.root, semgrep_dirs=("semgrep-foo",))
        self.assertEqual(ug.discover_valid_languages(self.root), {})


class ValidateLanguageTests(FilesystemTest):
    VALID = {"python": "python", "gomod": "gomod", "apex": "sfapex", "sfapex": "sfapex"}

    def test_returns_wrapper_for_direct_input(self):
        self.assertEqual(ug.validate_language("python", self.VALID), "python")

    def test_returns_wrapper_for_alias_input(self):
        # User passes "apex"; wrapper is "sfapex".
        self.assertEqual(ug.validate_language("apex", self.VALID), "sfapex")

    def test_dies_with_alias_hint_when_alias_target_passed(self):
        # "go-mod" is the SUBMODULE_ALIASES value for "gomod"; hint should fire.
        captured = StringIO()
        with redirect_stderr(captured), self.assertRaises(SystemExit) as cm:
            ug.validate_language("go-mod", self.VALID)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("did you mean 'gomod'", captured.getvalue())

    def test_dies_without_hint_for_unknown_language(self):
        captured = StringIO()
        with redirect_stderr(captured), self.assertRaises(SystemExit) as cm:
            ug.validate_language("xyz", self.VALID)
        self.assertEqual(cm.exception.code, 1)
        self.assertNotIn("did you mean", captured.getvalue())

    def test_dies_on_path_traversal_attempt(self):
        # Defensive: "..", "/", etc. must never resolve as valid languages.
        captured = StringIO()
        with redirect_stderr(captured), self.assertRaises(SystemExit) as cm:
            ug.validate_language("..", self.VALID)
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


class SyncLanguagesMembershipTests(FilesystemTest):
    def _setup_files(self) -> tuple[Path, Path]:
        """Create empty `languages-0.22.6` and `language-variants-0.22.6`."""
        langs = self.root / "languages-0.22.6"
        variants = self.root / "language-variants-0.22.6"
        langs.write_text("")
        variants.write_text("")
        return langs, variants

    def test_typescript_expands_to_variants(self):
        langs, variants = self._setup_files()
        ug.sync_languages_membership(
            self.root, "typescript", "0.22.6",
            {"0.22.6": langs}, {"0.22.6": variants},
        )
        self.assertEqual(ug.read_languages_entries(langs), {"typescript"})
        self.assertEqual(
            ug.read_languages_entries(variants), {"typescript", "tsx"},
        )

    def test_default_lang_appears_in_both_unchanged(self):
        langs, variants = self._setup_files()
        ug.sync_languages_membership(
            self.root, "python", "0.22.6",
            {"0.22.6": langs}, {"0.22.6": variants},
        )
        self.assertEqual(ug.read_languages_entries(langs), {"python"})
        self.assertEqual(ug.read_languages_entries(variants), {"python"})

    def test_alias_target_expands_to_variants(self):
        # "sfapex" (the wrapper name returned by validate_language when
        # the user passes "apex") expands to ["apex"] in LANGUAGE_VARIANTS.
        langs, variants = self._setup_files()
        ug.sync_languages_membership(
            self.root, "sfapex", "0.22.6",
            {"0.22.6": langs}, {"0.22.6": variants},
        )
        self.assertEqual(ug.read_languages_entries(langs), {"sfapex"})
        self.assertEqual(ug.read_languages_entries(variants), {"apex"})


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
        ug.remove_stale_parsers(self.root, "python", "python")
        self.assertFalse(outer.exists())
        self.assertFalse(inner.exists())

    def test_silent_when_targets_missing(self):
        # No parser files exist; function should not raise.
        ug.remove_stale_parsers(self.root, "python", "python")

    def test_lang_and_list_name_can_differ(self):
        # apex case: lang="apex" (lang/apex/), list_name="sfapex" (semgrep-sfapex/).
        outer = self._make_parser("lang", "apex", "src", "parser.c")
        inner = self._make_parser(
            "lang", "semgrep-grammars", "src", "semgrep-sfapex", "src",
            "parser.c",
        )
        ug.remove_stale_parsers(self.root, "apex", "sfapex")
        self.assertFalse(outer.exists())
        self.assertFalse(inner.exists())


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


# ----- Git-driven helpers (real-repo fixtures) -----------------------------


def _git(*args: str | Path, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run `git` in `cwd`, capturing stdout. Used only by test fixtures."""
    return subprocess.run(
        ["git", *[str(a) for a in args]],
        cwd=cwd, check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def init_git_repo(path: Path) -> str:
    """Initialize a repo at `path`, make one commit, return the commit SHA."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "commit.gpgsign", "false", cwd=path)
    # Permit file:// submodule URLs used by UpdateSubmoduleTests below.
    _git("config", "protocol.file.allow", "always", cwd=path)
    (path / "README").write_text("init\n")
    _git("add", "README", cwd=path)
    _git("commit", "-q", "-m", "init", cwd=path)
    return _git("rev-parse", "HEAD", cwd=path).stdout.strip()


class GitRepoTest(FilesystemTest):
    """Base class providing a real git repo at `self.repo` with one commit."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "repo"
        self.initial_sha = init_git_repo(self.repo)

    def current_branch(self, cwd: Path | None = None) -> str:
        return _git("branch", "--show-current", cwd=cwd or self.repo).stdout.strip()

    def head_sha(self, cwd: Path | None = None) -> str:
        return _git("rev-parse", "HEAD", cwd=cwd or self.repo).stdout.strip()

    def porcelain_status(self, cwd: Path | None = None) -> str:
        return _git("status", "--porcelain", cwd=cwd or self.repo).stdout.strip()


class EnsureOnBranchTests(GitRepoTest):
    def test_with_at_force_aligns_branch(self):
        ug.ensure_on_branch(self.repo, "my-branch", at=self.initial_sha)
        self.assertEqual(self.current_branch(), "my-branch")
        self.assertEqual(self.head_sha(), self.initial_sha)

    def test_no_op_when_already_on_branch(self):
        # init_git_repo leaves us on "main".
        ug.ensure_on_branch(self.repo, "main")
        self.assertEqual(self.current_branch(), "main")

    def test_creates_branch_when_missing(self):
        ug.ensure_on_branch(self.repo, "new-branch")
        self.assertEqual(self.current_branch(), "new-branch")
        self.assertEqual(self.head_sha(), self.initial_sha)

    def test_switches_to_existing_branch(self):
        _git("branch", "existing-branch", cwd=self.repo)
        ug.ensure_on_branch(self.repo, "existing-branch")
        self.assertEqual(self.current_branch(), "existing-branch")


class CommitChangesTests(GitRepoTest):
    def test_commits_when_changes_exist(self):
        (self.repo / "new.txt").write_text("hello\n")
        ug.commit_changes(self.repo, "python", "old12345", "new12345")
        self.assertNotEqual(self.head_sha(), self.initial_sha)
        message = _git("log", "-1", "--format=%s", cwd=self.repo).stdout.strip()
        self.assertEqual(
            message,
            "Update tree-sitter-python grammar from old12345 to new12345",
        )

    def test_skips_commit_when_clean(self):
        ug.commit_changes(self.repo, "python", "old12345", "new12345")
        self.assertEqual(self.head_sha(), self.initial_sha)


class RequireCleanWorktreeTests(GitRepoTest):
    def test_returns_when_clean(self):
        ug.require_clean_worktree(self.repo)  # should not raise

    def test_dies_when_dirty(self):
        (self.repo / "dirty.txt").write_text("oops\n")
        with self.assertRaises(SystemExit) as cm:
            ug.require_clean_worktree(self.repo)
        self.assertEqual(cm.exception.code, 1)


class UpdateSubmoduleTests(FilesystemTest):
    """Verify update_submodule against a real git submodule fixture.

    A separate "remote" repo with two commits acts as the submodule source.
    The outer repo adds it as a submodule pinned to the older commit so
    update_submodule has a real bump to perform.
    """

    SUBMODULE_REL = Path("lang") / "semgrep-grammars" / "src" / "tree-sitter-python"

    def setUp(self) -> None:
        super().setUp()
        self.outer = self.root / "outer"
        init_git_repo(self.outer)

        # Build the submodule source with two commits.
        self.remote = self.root / "remote"
        self.remote_old = init_git_repo(self.remote)
        (self.remote / "v2").write_text("v2\n")
        _git("add", "v2", cwd=self.remote)
        _git("commit", "-q", "-m", "v2", cwd=self.remote)
        self.remote_new = _git("rev-parse", "HEAD", cwd=self.remote).stdout.strip()

        # Attach as a submodule at the expected path, pinned to remote_old.
        # The `-c protocol.file.allow=always` must be on the command line:
        # the submodule clone uses git's startup-time config, not the parent
        # repo's config, so this can't be done via _git("config", ...).
        subprocess.run(
            ["git", "-c", "protocol.file.allow=always",
             "submodule", "add", "-f", str(self.remote), str(self.SUBMODULE_REL)],
            cwd=self.outer, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.submodule = self.outer / self.SUBMODULE_REL
        _git("checkout", "-q", self.remote_old, cwd=self.submodule)
        _git("config", "protocol.file.allow", "always", cwd=self.submodule)
        _git("add", str(self.SUBMODULE_REL), cwd=self.outer)
        _git("commit", "-q", "-m", "pin submodule", cwd=self.outer)

    def test_returns_old_and_new_sha(self):
        old, new = ug.update_submodule(
            self.submodule, self.outer, ref=self.remote_new, fetch=False,
        )
        self.assertEqual(old, self.remote_old)
        self.assertEqual(new, self.remote_new)

    def test_checks_out_new_sha_and_stages_gitlink(self):
        ug.update_submodule(
            self.submodule, self.outer, ref=self.remote_new, fetch=False,
        )
        new_head = _git("rev-parse", "HEAD", cwd=self.submodule).stdout.strip()
        self.assertEqual(new_head, self.remote_new)
        # Outer repo should have the gitlink update staged.
        staged = _git(
            "diff", "--cached", "--name-only", cwd=self.outer,
        ).stdout.strip().splitlines()
        self.assertIn(str(self.SUBMODULE_REL), staged)

    def test_no_checkout_when_sha_unchanged(self):
        old, new = ug.update_submodule(
            self.submodule, self.outer, ref=self.remote_old, fetch=False,
        )
        self.assertEqual(old, self.remote_old)
        self.assertEqual(new, self.remote_old)
        self.assertEqual(
            _git("rev-parse", "HEAD", cwd=self.submodule).stdout.strip(),
            self.remote_old,
        )
        # Nothing should be staged.
        self.assertEqual(
            _git("diff", "--cached", "--name-only", cwd=self.outer).stdout, "",
        )

    def test_fetch_picks_up_new_remote_commit(self):
        # Add a third commit to the remote that the submodule hasn't seen.
        (self.remote / "v3").write_text("v3\n")
        _git("add", "v3", cwd=self.remote)
        _git("commit", "-q", "-m", "v3", cwd=self.remote)
        remote_newer = _git("rev-parse", "HEAD", cwd=self.remote).stdout.strip()

        # With fetch=True, update_submodule resolves the new ref and checks it out.
        old, new = ug.update_submodule(
            self.submodule, self.outer, ref=remote_newer, fetch=True,
        )
        self.assertEqual(old, self.remote_old)
        self.assertEqual(new, remote_newer)
        self.assertEqual(
            _git("rev-parse", "HEAD", cwd=self.submodule).stdout.strip(),
            remote_newer,
        )

    def test_fetch_skipped_when_disabled(self):
        # Add a new commit to remote, but with fetch=False the submodule
        # can't resolve it and update_submodule should fail at rev-parse.
        (self.remote / "v3").write_text("v3\n")
        _git("add", "v3", cwd=self.remote)
        _git("commit", "-q", "-m", "v3", cwd=self.remote)
        remote_newer = _git("rev-parse", "HEAD", cwd=self.remote).stdout.strip()

        with self.assertRaises(subprocess.CalledProcessError):
            ug.update_submodule(
                self.submodule, self.outer, ref=remote_newer, fetch=False,
            )


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
