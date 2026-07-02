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

This repo extends each upstream `tree-sitter-<lang>` grammar with semgrep
pattern constructs — ellipsis `...`, metavariables `$X`, deep ellipsis
`<... e ...>`, typed/variadic metavariables, alternate entry points, and
friends — in `lang/semgrep-grammars/src/semgrep-<lang>/grammar.js`, via
`($, previous) => ...` rule overrides. Rule names vary per language; the full
name inventory is in [references/semgrep-constructs.md](references/semgrep-constructs.md).
When upstream changes, the extension stops matching and `test-lang` fails.
**Make `test-lang <lang>` pass with the smallest correct change to the
extension grammar and its tests.**

## Inputs

- **`<lang>`** — the `test-lang` argument (e.g. `javascript`, `solidity`). The
  sublanguage set it builds is hardcoded in the `sublangs=` block of
  `lang/test-lang` — read it there (currently `typescript`→`typescript tsx`,
  `php`→`php php-only`, `sfapex`→`apex`, `cfml`→`cfml`, everything else → the
  lang itself). Steps 1 and 4 act on whichever directories it builds.
- **Repo root** — `git rev-parse --show-toplevel`. Never hardcode an absolute path.
- **(optional) `max-iterations`** — caps the loop; default **20**. One
  iteration = one step-7 fix plus its step-4 re-run (the initial baseline run
  doesn't count; the step-3 rename batch counts as one). The default is a
  guess, not empirical — the worst run measured so far (Solidity) needed ~6
  fixes; the cap exists to stop runaway loops, not to be approached. Reaching
  it is a normal, logical stop (see Exit contract).
- **(optional) Budget hint** — advisory only; bias toward landing a minimal fix
  and stopping. The harness owns hard time/turn/cost limits.

## The loop

1. **Check for uncommitted changes** (precondition, from the repo root):
   ```
   git status --porcelain --ignored -- lang/semgrep-grammars/src/semgrep-<lang> lang/<sublang-1> lang/<sublang-2> ...
   ```
   using the sublanguage set from Inputs (`--ignored` matters — plain status
   won't list the ignored files `git clean -dfX` deletes). `test-lang` runs
   `make clean` in each of these directories on every iteration, and `make
   clean` there is `git clean -dfX`: it force-deletes every git-ignored file
   under the tree, no confirmation. Normally that's regenerable build output
   (`src/`, `test.log`, `CST.ml`, `ocaml-src`, …), but don't assume. If the
   status reports anything — tracked changes *or* untracked/ignored files —
   **stop, list exactly what `git clean -dfX` would remove (noting which files
   are recognizably generated: generated-file headers, standard artifact
   names), and ask the user to confirm.** A clean tree needs no confirmation.

2. **Require the toolchain** (precondition, from the repo root). The
   tree-sitter version for `<lang>` is pinned in `lang/languages-*`; verify it,
   never install it (installing mutates shared `core/` state — that's the
   harness's job):
   ```
   v=$(lang/scripts/ts-version-for-lang <lang>)
   [ -x core/tree-sitter-$v/bin/tree-sitter ] || \
     { echo "tree-sitter $v is not installed for <lang> — cannot proceed"; exit 1; }
   ```
   If missing, stop with `CANNOT_PROCEED`, reporting the version and the
   install command for the harness to run: `cd core &&
   ./scripts/switch-tree-sitter-version <v> && ./scripts/install-tree-sitter-cli
   && ./scripts/install-tree-sitter-lib`.

3. **Statically pre-diagnose broken references, once, before the first run.**
   `tree-sitter generate` reports only the first broken reference per
   invocation, so find them all by name up front:
   ```
   grep -oE '\$\.\w+' lang/semgrep-grammars/src/semgrep-<lang>/grammar.js | sort -u
   ```
   First discard names the extension itself declares (keys of its own
   `rules: {}`) — those are self-owned and will never appear upstream. Check
   each remaining name still resolves in the *current*
   `lang/semgrep-grammars/src/tree-sitter-<lang>/grammar.js` (adjust for quoted
   keys / declaration style). Each name that doesn't is a candidate
   rename/promotion — diagnose it per step 6, proactively. Apply the verified
   rename queue as a **single batched fix** — renames are one fix class and
   `generate` validates them together; everything else stays one fix per
   iteration (step 7).

   A rename fix has two parts, applied together as one edit: the `grammar.js`
   reference *and* every semgrep-owned corpus case naming the old node:
   ```
   grep -rn "(<old>" lang/semgrep-grammars/src/semgrep-<lang>/test/corpus/*.txt
   ```
   (never `test/corpus/inherited` — that's upstream's own corpus). Corpus
   substitutions are drafts until verified against actual output once
   `test-lang` runs — an upstream rename isn't guaranteed pure. This pass only
   catches "this name no longer exists"; conflicts, corpus drift, and symbols
   that still resolve but changed meaning surface only in step 4.

4. **Run** (from the `lang/` dir, not the repo root):
   ```
   cd lang && ./test-lang <lang>
   ```
   In order: (a) build + `tree-sitter test` corpus tests in
   `semgrep-grammars/src/semgrep-<lang>/`, (b) `parse-examples` per sublang —
   the generated parser over real files in `lang/<sublang>/test/{ok,xfail}` —
   (c) a Blank-node check per sublang. Each directory is `git clean -dfX`'d
   first (step 1). Success = **exit code 0 and no new Blank-node warnings vs.
   the baseline**.

   **Blank-node baseline:** the check greps generated `ocaml-src/lib/CST.ml`,
   so it can only report on a run that builds far enough to produce that file;
   it is advisory and never affects `test-lang`'s exit code. If the **first**
   run (before any edit) reaches the check for a sublang, its warnings are
   that sublang's baseline — those pre-existing Blank nodes are out of scope,
   and fixing one would violate "smallest correct edit". If the first run
   fails before the check, the baseline is **empty**: `SUCCESS` then requires
   no Blank-node warnings at all. On later runs, only warnings not in the
   baseline count against `SUCCESS`.

5. **Classify** the first failure:

   | Symptom | Meaning |
   |---|---|
   | `tree-sitter generate` errors | grammar.js references a rule upstream renamed/removed, or the overrides create an unresolved conflict (the error names the rule) |
   | corpus test diff (expected vs actual S-expr) | expected tree ≠ actual — either a legitimate upstream change or a regression from your own earlier edit; step 6 decides which |
   | example in `test.out/fail.list` — entries are paths relative to `lang/<sublang>/test/ok/`; each CST dump is at `test.out/ok/<entry>.cst` (look for `!ERROR!`/`ERROR`) | a real source file no longer parses |
   | Blank-node warning not in the baseline | a node your edit introduced or exposed produces no tokens — give it a named rule |
   | tree-sitter version/ABI errors (grammar needs a newer tree-sitter than the pin, ABI mismatch) | the `lang/languages-*` pin is stale, not a grammar bug — out of scope: `CANNOT_PROCEED`, reporting the version-list change needed |

6. **Diagnose against upstream** — match each rule you override to its
   *current* definition in `lang/semgrep-grammars/src/tree-sitter-<lang>/grammar.js`
   and check what changed:
   `git -C lang/semgrep-grammars/src/tree-sitter-<lang> log --oneline -5`.
   For example failures, the `.cst` dump shows which node became `ERROR`.
   Don't guess.

7. **Apply the smallest correct edit** (playbook below), one logical fix at a
   time — the sole exception is the step-3 rename queue, which lands as one
   batched fix. A fix includes its corpus updates: a rename carries its corpus
   substitutions (step 3), and a new/changed rule override carries its corpus
   case (coverage invariant, Edit boundaries). To derive and verify a corpus
   expectation without burning an iteration: `make` in `semgrep-<lang>/`, then
   `core/tree-sitter-<v>/bin/tree-sitter parse <snippet>` for the actual tree
   and `tree-sitter test --include '<case name>'` for the case — then re-run
   `test-lang` to confirm end to end.

8. **Re-run** step 4. Repeat until exit 0, or until `max-iterations` is spent —
   whichever comes first. Hitting the cap is a normal stop: go to Exit.

9. **Exit** per the contract below.

## Edit boundaries

**May edit (only these):**
- `lang/semgrep-grammars/src/semgrep-<lang>/grammar.js`
- semgrep-owned corpus files `lang/semgrep-grammars/src/semgrep-<lang>/test/corpus/*.txt`
  — **never** the `inherited` symlink (it points at the upstream corpus). If no
  semgrep-owned file exists yet, create `test/corpus/semgrep.txt`; match the
  inherited corpus's S-expression style (e.g. no field names).

**Coverage invariant: every rule override you add or change must be exercised
by at least one semgrep-owned corpus case, added or extended in the same
edit.** A corpus case is the only test that pins the exact S-expression
(`parse-examples` only checks that a file parses without `ERROR`/`MISSING`),
so it's the only thing that catches "still parses, but the shape changed".
Don't defer the case, and don't count an incidental `test/ok` example as
coverage. Pre-existing overrides that lack coverage are out of scope — don't
backfill them; list them in the exit summary for a human to triage.

**Never edit:** `tree-sitter-<lang>/` (the submodule, including `scanner.c`);
the `lang/languages-*` / `language-variants-*` version lists or the submodule
pointer; anything in the CST→AST / OCaml codegen or the `semgrep` proprietary
repo; the `inherited` corpus symlink.

**Never weaken semgrep semantics or tests to go green.** Never delete, skip,
or relocate a test (e.g. into `test/xfail/`); never delete a semgrep
construct; never rewrite an expected corpus tree just to silence a failure —
expected trees change only to reflect a *legitimate* upstream structural
change. A case you cannot make pass with a legitimate grammar change is
`CANNOT_PROCEED` (see Exit) — unless upstream deliberately dropped the syntax,
in which case ask the user first (see the playbook's last entry).

## Fix playbook

Common shapes when an upstream bump breaks the extension:

- **Rule renamed upstream** → update every reference (often a `_` added/dropped:
  `_statement`↔`statement`; or a typo fix: `event_paramater`→`event_parameter`).
- **Rule promoted to a top-level upstream declaration** → your override now
  makes it reachable twice (generate conflict); drop the redundant entry. In
  an entry-point override, check each alternative individually — drop only
  the ones upstream now makes reachable; the rest must stay.
- **You copy-pasted a base rule to splice in ellipsis, and upstream refactored
  it** → stop copying; extend the new upstream rule with `($, previous) =>`.
  Delete orphaned copied helpers.
- **Corpus tree drifted** from a legitimate upstream change → update the
  expected S-expr in `test/corpus/*.txt` to match; verify against the actual
  tree, don't blindly paste.
- **Stale `// TODO: use PREC.X`** for a constant that isn't exported → don't
  re-investigate: upstream `PREC` tables are module-local `const`s the
  extension can never reference, and `prec.dynamic` doesn't resolve a static
  LR conflict. If you must hardcode a precedence, replace the TODO with the
  one-line reason.
- **New parse conflict** (generate error names two rules, not a missing one) →
  resolve it in the extension grammar with the most specific
  `prec`/`prec.dynamic` or `conflicts: [...]` entry that works; don't restate
  upstream rules to dodge it.
- **Failure traces to an external token** — one listed in upstream's
  `externals:` array and produced by `scanner.c` → first check whether
  extending a rule in `grammar.js` can route around it (semgrep-javascript's
  `_jsx_child` works around a scanner limitation in-bounds); if the fix truly
  requires scanner changes, `CANNOT_PROCEED`, naming the token.
- **Upstream changed the `word:`/identifier token** → metavariables folded into
  `identifier` may stop lexing; re-fold them against the new identifier rule.
  If `$X` can no longer be admitted without scanner changes, `CANNOT_PROCEED`.
- **New upstream syntax collides with a semgrep construct** (e.g. upstream adds
  real `...` or `$`-prefixed names) → try precedence/token ordering so both
  survive; if the construct can't be disambiguated without weakening it,
  `CANNOT_PROCEED`.
- **Upstream restructured its grammar file layout** (e.g. a dialect factory
  like `common/define-grammar.js`) → update the extension's
  `require(...)`/wrapping to the new entry point; the rule overrides themselves
  may need no change.
- **Upstream deliberately dropped syntax**, so a `test/ok` example or corpus
  case is legitimately no longer parseable → do **not** move it to `xfail`,
  delete it, or rewrite it on your own: **warn the user, state exactly what
  upstream dropped and which tests it strands, and ask how to proceed.** If no
  one can answer (unattended run), exit `CANNOT_PROCEED` with that question as
  the blocker.

Prefer extending over replacing, and replacing over copy-pasting — the less of
the upstream rule you restate, the less drifts next time.

## Exit contract

A **logical** stop, or the `max-iterations` cap — never a resource cap invented
on the fly. Print one unmistakable line:

- **`FIX-SEMGREP-GRAMMAR: SUCCESS`** — `test-lang <lang>` exits 0, the coverage
  invariant holds for every override you touched, and no new Blank-node
  warnings vs. the baseline. Summarize the edits (files, fix class, why),
  which corpus case covers which touched rule, the baseline you captured, and
  any pre-existing uncovered overrides you did not backfill, for the PR
  reviewer.
- **`FIX-SEMGREP-GRAMMAR: CANNOT_PROCEED`** — no progress for a logical reason:
  the real fix needs an out-of-scope change (submodule/scanner, translation,
  version bump), the failure isn't a grammar issue, or fixing it would weaken
  semgrep semantics. State the blocker, what you tried, and the smallest change
  that *would* fix it if the boundary were lifted.
- **`FIX-SEMGREP-GRAMMAR: ITERATION_LIMIT`** — `max-iterations` was spent
  without reaching exit 0. Summarize every edit tried, the current failure, and
  your best guess at the next edit, so a human or a fresh run can pick it up.

Do **not** commit, push, or open a PR unless asked. Leave the working tree
changed for the outer grammar-update pipeline's PR-review stage — no
auto-merge.

## Running by hand

From the repo, give the agent the language and this skill, e.g.
`Use fix-semgrep-grammar to make test-lang javascript pass.` — optionally with
a tighter cap, e.g. `... pass, with max-iterations 5.` Under the Claude Agent
SDK (e.g. a Python GitHub Action), keep the hard limits (`max_turns`, budget,
an outer `timeout`) at the harness level — `max-iterations` bounds only the fix
loop. The tree-sitter toolchain is a precondition the harness provisions (step
2 only verifies it). Unattended runs should start from a clean checkout or
explicitly pre-approve step 1's confirmation — never silently auto-confirm on
the skill's behalf.
