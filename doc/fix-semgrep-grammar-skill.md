# fix-semgrep-grammar: the grammar-repair agent skill

An agent skill (`.agents/skills/fix-semgrep-grammar/SKILL.md`) that repairs
the semgrep extension grammar after an upstream tree-sitter bump, iterating
until `test-lang <lang>` passes.

## Inputs

- `<lang>` — the `test-lang` argument (e.g. `typescript`).
- *(optional)* `max-iterations` — caps the fix/re-run loop; default 20.
- *(optional)* a budget hint — advisory; biases toward a minimal fix.

## Where it operates

It edits only `lang/semgrep-grammars/src/semgrep-<lang>/grammar.js` and the
semgrep-owned corpus files `.../test/corpus/*.txt`. It never touches the
upstream submodule (including `scanner.c`), the `lang/languages-*` version
pins, or the CST→AST / OCaml codegen, and it never commits or opens PRs.

## Running it by hand

Give an agent the language and the skill:

    Use fix-semgrep-grammar to make test-lang typescript pass.

Optionally add a tighter cap: `... pass, with max-iterations 5.` The skill
asks for confirmation before letting `test-lang` run `git clean -dfX` over a
dirty tree.

## Exit statuses

The skill always ends with one machine-readable line:

- `FIX-SEMGREP-GRAMMAR: SUCCESS` — `test-lang` exits 0, new/changed overrides
  have corpus coverage, no new Blank nodes.
- `FIX-SEMGREP-GRAMMAR: CANNOT_PROCEED` — the real fix is outside the skill's
  edit boundaries (with the blocker stated).
- `FIX-SEMGREP-GRAMMAR: ITERATION_LIMIT` — the cap was reached; the summary
  lets a human or a fresh run pick up.

## Limits

The skill is SKILL.md instructions only: it stops for logical reasons but
cannot enforce turn, cost, or wall-clock limits — run it under harness-level
caps (`max_turns`, budget, an outer timeout).
