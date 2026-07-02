---
name: fix-semgrep-grammar
description: >-
  Fix the Semgrep extension grammar for a language until `test-lang <lang>`
  passes. Use when the semgrep grammar build/test fails — typically after an
  upstream tree-sitter grammar was bumped: parser-generation errors, corpus
  mismatches, failed example files, or Blank-node warnings under
  `lang/semgrep-grammars/src/semgrep-<lang>/`. This is "step 4" of the
  grammar-update process. Edits only this repo's semgrep grammar/tests; never
  the upstream submodule or the CST→AST translation.
---

# Fix the Semgrep grammar (step 4)

This repo extends each upstream `tree-sitter-<lang>` grammar with the Semgrep
pattern constructs below, in `lang/semgrep-grammars/src/semgrep-<lang>/grammar.js`,
via `($, previous) => ...` rule overrides. When upstream changes, the extension
stops matching and `test-lang` fails. **Make `test-lang <lang>` pass with the
smallest correct change to the extension grammar and its tests.**

The semgrep constructs to recognize and preserve (rule names vary per language —
this is the full family seen across the wrappers):

- **Ellipsis** `...` — `ellipsis` / `semgrep_ellipsis`; spliced in as a statement,
  expression, parameter/argument, and list element (e.g. `catch_ellipsis`,
  `semgrep_ellipsis_and_comma`, `semgrep_ellipsis_followed_by_newline`).
- **Named ellipsis** — `semgrep_named_ellipsis`.
- **Deep ellipsis** `<... e ...>` — `deep_ellipsis` / `semgrep_deep_ellipsis` /
  `semgrep_deep_expression`.
- **Metavariables** `$X` — `_semgrep_metavariable` / `semgrep_metavariable`,
  usually folded into the base `identifier` rule.
- **Typed metavariables** `(T $X)` — `typed_metavariable` / `semgrep_typed_metavar`
  (+ `typed_metavariable_declaration`).
- **Variadic / ellipsis metavariables** `$...X` — `semgrep_variadic_metavariable` /
  `semgrep_ellipsis_metavariable` / `_semgrep_metavar_ellipsis`.
- **Member-/field-access ellipsis** `x. ...` — `member_access_ellipsis_expression`
  / `member_ellipsis_expression` / `field_access_ellipsis_expr`.
- **Metavariable assignment** `$X = ...`, `$X += ...` — `semgrep_metavar_eq` /
  `semgrep_metavar_pluseq` (+ `semgrep_val_or_var_definition`).
- **Alternate entry points** letting a pattern be a bare fragment —
  `semgrep_expression` / `semgrep_statement` / `semgrep_pattern` /
  `semgrep_partial`, added to the grammar's start rule (sometimes guarded by a
  `__SEMGREP_*` token).

## Inputs

- **`<lang>`** — the `test-lang` argument (e.g. `javascript`, `solidity`). Some
  languages build a different sublanguage set under `lang/`: `typescript`→
  `typescript tsx`, `php`→`php php-only`, `sfapex`→`apex` (**not** `sfapex`),
  `cfml`→`cfml`. `test-lang` computes this; steps 1 and 4 act on whichever
  directories it actually builds, not necessarily `lang/<lang>` itself.
- **Repo root** — `git rev-parse --show-toplevel`; accept a caller override. Never
  hardcode an absolute path.
- **(optional) `max-iterations`** — caps the fix/re-run loop (step 8). Default
  **8** if not given. Enforced by the skill itself — unlike the Budget hint
  below, reaching it is a normal, logical stop (see Exit contract).
- **(optional) Budget hint** — advisory only. Bias toward landing a minimal fix and
  stopping. You cannot enforce time/turn/cost limits; the harness owns those.

## The loop

1. **Check for uncommitted changes** (precondition, from the repo root):
   ```
   git status --porcelain -- lang/semgrep-grammars/src/semgrep-<lang> lang/<sublang-1> lang/<sublang-2> ...
   ```
   using the sublanguage set from Inputs (usually just `<lang>` itself — see
   the exceptions there, e.g. `sfapex` needs `lang/apex`, not `lang/sfapex`).
   `test-lang` runs `make clean` in every one of these directories on
   **every** iteration of this loop (step 4), and `make clean` there is `git
   clean -dfX` — it force-deletes every git-ignored file under that tree, no
   confirmation, no matter what's actually in it. In this repo that's
   normally just regenerable build output (`src/`, `test.log`, `CST.ml`,
   `ocaml-src`, …), but the skill has no way to verify that's still true for
   an arbitrary `<lang>`, or whether the user left something there they care
   about. If `git status --porcelain` reports anything under any of these
   paths (tracked changes *or* untracked-but-ignored files), **stop and tell
   the user exactly what `git clean -dfX` would remove, and ask them to
   confirm before proceeding.** Don't assume it's disposable. A clean tree
   needs no confirmation.

2. **Require the toolchain** (precondition, from the repo root). The tree-sitter
   version for `<lang>` is pinned in `lang/languages-*`. Verify it is installed; if
   not, stop with `CANNOT_PROCEED` — provisioning it is the harness's job, not this
   skill's (installing mutates shared `core/` state):
   ```
   v=$(lang/scripts/ts-version-for-lang <lang>)
   [ -x core/tree-sitter-$v/bin/tree-sitter ] || \
     { echo "tree-sitter $v is not installed for <lang> — cannot proceed"; exit 1; }
   ```
   Report the missing version and the install command the harness should run:
   `cd core && ./scripts/switch-tree-sitter-version <v> && ./scripts/install-tree-sitter-cli && ./scripts/install-tree-sitter-lib`.

3. **Statically pre-diagnose generate-time breakage, once, before the first
   run** (from the repo root). `tree-sitter generate` reports only the first
   broken reference per invocation — it cannot reveal a second broken
   override until the first is fixed and regenerated, which otherwise forces
   one full iteration of this loop per rename just to discover the next one.
   Front-load whatever's discoverable by name before that happens:
   ```
   grep -oE '\$\.\w+' lang/semgrep-grammars/src/semgrep-<lang>/grammar.js | sort -u
   ```
   For each `$.<name>` this finds, check it's still declared in the *current*
   upstream grammar (adjust for quoted keys / declaration style):
   ```
   grep -n "<name>" lang/semgrep-grammars/src/tree-sitter-<lang>/grammar.js
   ```
   Any override referencing a name that no longer resolves is a candidate
   rename/promotion — diagnose it the same way as step 6 (match against
   upstream's *current* definition, check its recent history), just
   proactively instead of reactively.

   **A rename found this way needs two edits, not one.** Renaming `<old>` to
   `<new>` in `grammar.js` fixes `generate`, but any semgrep-owned corpus case
   whose expected S-expression names `<old>` (e.g. `(<old> ...)`) will then
   fail `tree-sitter test` on the very next run — that text doesn't update
   itself. Before running `test-lang` for the first time, also:
   ```
   grep -rn "(<old>" lang/semgrep-grammars/src/semgrep-<lang>/test/corpus/*.txt
   ```
   (never `test/corpus/inherited` — that's upstream's own corpus and already
   matches upstream's rename) and batch-substitute `<old>`→`<new>` in every
   hit. Treat this as a **draft**, not a confirmed fix: a rename upstream
   isn't guaranteed to be *pure* — the shape or fields around it can change
   too — so these substitutions still need verifying against the actual
   output tree once `test-lang` runs, same as any other corpus update (see
   "Corpus tree drifted" in the Fix playbook). Batch every `grammar.js` and
   corpus fix this pass finds into a single edit before running `test-lang`
   for the first time.

   This is a heuristic first pass, not a substitute for step 6 or 5: it only
   catches breakage that shows up as "this exact name no longer exists," and
   its corpus substitutions are provisional until verified. It won't catch
   new conflicts, corpus drift from a non-rename cause, or a symbol that
   still resolves but now means something different — those still only
   surface once you actually run `test-lang`, in step 4.

4. **Run** (from the `lang/` dir, not the repo root):
   ```
   cd lang && ./test-lang <lang>
   ```
   It runs, in order: (a) build + `tree-sitter test` corpus tests in
   `semgrep-grammars/src/semgrep-<lang>/`, then (b) `parse-examples` for each
   sublang — the generated parser run over real files in
   `lang/<sublang>/test/{ok,xfail}` — then (c) a Blank-node check per sublang
   (see below). `semgrep-grammars/src/semgrep-<lang>/` and every sublang
   directory are each `make clean`'d (`git clean -dfX` — see step 1) before
   being rebuilt. Success = **exit code 0** (no unexpected results) **and no
   new Blank-node warnings** (see baseline, below).

   **Blank-node baseline:** `test-lang`'s Blank-node check (per sublang, grep
   for `Blank` in `ocaml-src/lib/CST.ml`) is advisory — it never affects
   `test-lang`'s own exit code. The **first time you run step 4, before any
   edit from step 7**, record whatever Blank-node warnings it prints as the
   **baseline**: pre-existing Blank nodes are not this run's problem to fix,
   and fixing one anyway would violate "smallest correct edit." If that first
   run fails before reaching the Blank-node check (e.g. a `tree-sitter
   generate` or corpus error upstream of it), treat the baseline as
   unknown/empty for that sublang and say so in the exit summary — don't
   assume it's clean. On every later run, compare the warnings against the
   baseline: only *new* ones (not present at baseline) count against
   `SUCCESS`.

5. **Classify** the first failure:

   | Symptom | Meaning |
   |---|---|
   | `tree-sitter generate` errors | grammar.js references a rule upstream renamed/removed, or overrides create an unresolved conflict (error names the rule) |
   | corpus test diff (expected vs actual S-expr) | a `test/corpus/*.txt` expected tree no longer matches a legitimate upstream change |
   | example in `test.out/fail.list` (CST dumped to `test.out/**/<file>.cst`, look for `!ERROR!`/`ERROR`) | a real source file no longer parses |
   | Blank-node warning **not in the step-4 baseline** | a node your edit introduced or exposed produces no tokens — give it a named rule |

   A Blank-node warning that *was already in the baseline* is pre-existing and
   out of scope for this run — leave it alone.

6. **Diagnose against upstream** — match each rule you override to its *current*
   upstream definition; don't guess. Read
   `lang/semgrep-grammars/src/tree-sitter-<lang>/grammar.js` for the named rule and
   check what changed: `git -C lang/semgrep-grammars/src/tree-sitter-<lang> log --oneline -5`.
   For example failures, the `.cst` dump shows exactly which node became `ERROR`.

7. **Apply the smallest correct edit** (playbook below). Change one thing at a
   time. If the edit adds or changes a rule override, add or extend its corpus
   case in the same step — see the coverage invariant under Edit boundaries.

8. **Re-run** step 4. Repeat until exit 0, or until `max-iterations` attempts
   (default **8**) are spent — whichever comes first. Hitting the cap is a
   normal, logical stop, not a failure to paper over: go to Exit.

9. **Exit** per the contract below.

## Edit boundaries

**May edit (only these):**
- `lang/semgrep-grammars/src/semgrep-<lang>/grammar.js`
- semgrep-owned corpus files `lang/semgrep-grammars/src/semgrep-<lang>/test/corpus/*.txt` — **never** the `inherited` symlink (it points at the upstream corpus).

**Coverage invariant: every rule override in `grammar.js` — every key in the
`rules: {}` object — must be exercised by at least one case in the
semgrep-owned corpus.** `test-lang`'s `parse-examples` step only asserts that
a file parses without an `ERROR`/`MISSING` node (an exit-code check on the
whole file); it does not assert *what* tree comes out. A corpus case is the
only thing in this toolchain that pins the exact expected S-expression, so
it's the only thing that catches "still parses, but the shape changed"
regressions. When you add or change a rule override, add or extend its corpus
case in the same edit — don't defer it, and don't rely on an incidental
`test/ok` example file being enough (it wasn't written to protect this rule
and can be moved/pruned without anyone noticing the coverage went with it).

**Never edit:** `tree-sitter-<lang>/` (the submodule, including `scanner.c`); the
`lang/languages-*` / `language-variants-*` version lists or the submodule pointer;
anything in the CST→AST / OCaml codegen or the `semgrep` proprietary repo; the
`inherited` corpus symlink.

**Never weaken semgrep semantics or tests to go green.** Specifically: never
delete, skip, or relocate a test (e.g. moving an example to `test/xfail/`) to make
the run pass artificially; never delete a semgrep construct; never rewrite an
expected corpus tree just to silence a failure. Expected trees change only to
reflect a *legitimate* upstream structural change. A case you cannot make pass with
a legitimate grammar change is `CANNOT_PROCEED` (see Exit) — not a test you remove.

## Fix playbook

Common shapes when an upstream bump breaks the extension:

- **Rule renamed upstream** → update every reference (often a `_` added/dropped:
  `_statement`↔`statement`; or a typo fix: `event_paramater`→`event_parameter`).
- **Rule promoted to a top-level upstream declaration** → your override now
  double-defines it (generate conflict); drop the redundant entry.
- **You copy-pasted a base rule to splice in ellipsis, and upstream refactored it**
  → stop copying; extend the new upstream rule with `($, previous) =>`. Delete
  orphaned copied helpers.
- **Corpus tree drifted** from a legitimate upstream change → update the expected
  S-expr in `test/corpus/*.txt` to match; verify against the actual tree, don't
  blindly paste.
- **Stale `// TODO: use PREC.X`** for a constant that isn't exported → if you must
  hardcode a precedence, replace the TODO with the one-line reason.
- **New parse conflict** (generate error names two rules, not a missing one) →
  resolve it in the extension grammar with the most specific `prec`/`prec.dynamic`
  or `conflicts: [...]` entry that works; don't restate upstream rules to dodge it.
- **Failure traces to an external token** — one listed in upstream's `externals:`
  array and produced by `scanner.c` → the real fix lives in the scanner, which is
  out of scope: `CANNOT_PROCEED`, naming the token.
- **Upstream changed the `word:`/identifier token** → metavariables folded into
  `identifier` may stop lexing; re-fold them against the new identifier rule. If
  `$X` can no longer be admitted without scanner changes, `CANNOT_PROCEED`.
- **New upstream syntax collides with a semgrep construct** (e.g. upstream adds
  real `...` or `$`-prefixed names) → try precedence/token ordering so both
  survive; if the construct can't be disambiguated without weakening it,
  `CANNOT_PROCEED`.
- **Upstream restructured its grammar file layout** (e.g. a dialect factory like
  `common/define-grammar.js`) → update the extension's `require(...)`/wrapping to
  the new entry point; the rule overrides themselves may need no change.
- **Upstream deliberately dropped syntax**, so a `test/ok` example or corpus case
  is legitimately no longer parseable → do **not** move it to `xfail`, delete it,
  or rewrite it on your own: **warn the user, state exactly what upstream dropped
  and which tests it strands, and ask how to proceed.** If no one can answer
  (unattended run), exit `CANNOT_PROCEED` with that question as the blocker.

Prefer extending over replacing, and replacing over copy-pasting — the less of the
upstream rule you restate, the less drifts next time.

## Exit contract

A **logical** stop, or the `max-iterations` cap (step 8) being reached — never a
resource cap invented on the fly. Print one unmistakable line:

- **`FIX-SEMGREP-GRAMMAR: SUCCESS`** — `test-lang <lang>` exits 0, every rule
  override in `grammar.js` has a corpus case (the coverage invariant under
  Edit boundaries), **and** no new Blank-node warnings vs. the step-4 baseline.
  Summarize the edits (files, fix class, why), which corpus case covers which
  rule, and the Blank-node baseline you captured, for the PR reviewer.
- **`FIX-SEMGREP-GRAMMAR: CANNOT_PROCEED`** — no progress for a logical reason: the
  real fix needs an out-of-scope change (submodule/scanner, translation, version
  bump), the failure isn't a grammar issue, or fixing it would weaken semgrep
  semantics. State the blocker, what you tried, and the smallest change that *would*
  fix it if the boundary were lifted.
- **`FIX-SEMGREP-GRAMMAR: ITERATION_LIMIT`** — `max-iterations` attempts were spent
  without reaching exit 0. Summarize every edit tried, the current failure, and your
  best guess at the next edit, so a human or a fresh run can pick it up.

Do **not** commit, push, or open a PR unless asked. Leave the working tree changed
for the surrounding grammar-update process's later PR-review stage (a separate,
outer pipeline from this skill's own numbered steps 1-9 above — the numbering
isn't shared) to carry into a PR for human review — no auto-merge.

## Running by hand

From the repo, give the agent the language and this skill, e.g.
`Use fix-semgrep-grammar to make test-lang javascript pass.` Add a tighter cap if you
want one, e.g. `... pass, with max-iterations 5.` Under the Claude Agent SDK (e.g. a
Python GitHub Action), invoke with this skill available and enforce the hard limits
(`max_turns`, budget, an outer `timeout`) at the harness level — `max-iterations`
bounds the fix loop itself, not turns/tokens/wall-clock, so keep the harness-level
limits too.

**Toolchain:** `test-lang` needs the per-language tree-sitter version built. This is
a **precondition the harness provisions** (via the `core/scripts` installers); the
skill only verifies it (step 2) and reports `CANNOT_PROCEED` if it's missing — it
never installs it, and never works around a missing toolchain by editing grammar.js.

**Uncommitted state:** step 1 will stop and ask before letting `test-lang` run
`git clean -dfX` over any dirty `semgrep-<lang>` or sublang tree it's about to
rebuild. If running unattended (no one to answer the confirmation), the
harness should either start from a clean checkout or pre-approve/skip step 1
explicitly — don't silently auto-confirm on the skill's behalf.
