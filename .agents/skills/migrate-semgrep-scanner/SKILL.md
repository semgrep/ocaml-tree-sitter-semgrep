---
name: migrate-semgrep-scanner
description: >-
  Replace a stale Semgrep C++ external scanner (scanner.cc) with upstream's C
  scanner.c plus Semgrep-specific extensions, so the language can use
  tree-sitter >= 0.24. Use when propose-grammar-update / the language agent
  reports that semgrep-<lang>/src/scanner.cc is still C++ while upstream
  already ships scanner.c, or when unlocking a tree-sitter pin past 0.24.0
  for that reason.
---

# Migrate Semgrep external scanner C++ → C

Some Semgrep wrappers still force-track a C++ `src/scanner.cc` after upstream
moved to `src/scanner.c`. Tree-sitter ≥ 0.24 does not support C++ scanners, so
`propose-grammar-update` caps those languages below 0.24 until this migration
runs.

**Replace the wrapper's C++ scanner with upstream's C scanner at the bumped
tag, re-apply only Semgrep-specific lexer extensions, force-add the new file,
and delete `scanner.cc`.** Then stop — corpus/grammar repair is
`fix-semgrep-grammar`'s job.

## Inputs

- **`<lang>`** — the `test-lang` / propose language name (e.g. `ruby`).
- **Repo root** — `git rev-parse --show-toplevel`. Never hardcode an absolute path.
- **Upstream tag** (from the outer propose bump) — the submodule is already at
  this tag when the harness calls you.

## Preconditions

1. Wrapper path: `lang/semgrep-grammars/src/semgrep-<wrapper>/` (usually
   `wrapper == lang`; read `propose-grammar-update` / `update-grammar` if unsure).
2. Confirm wrapper still has `src/scanner.cc`.
3. Confirm upstream submodule `lang/semgrep-grammars/src/tree-sitter-<lang>/`
   (path may differ for e.g. `gomod` → `tree-sitter-go-mod`) has `src/scanner.c`.
4. If upstream still only has `scanner.cc`, exit `CANNOT_PROCEED` — this skill
   cannot invent a C port of upstream.

## Steps

1. **Inventory Semgrep extensions** in the wrapper `scanner.cc`: tokens /
   `TokenType` entries and `scan` cases marked `sgrep-ext` / `SEMGREP_*`, plus
   any matching `externals:` entries in `grammar.js`. Do not invent new
   Semgrep tokens.

2. **Copy** upstream `tree-sitter-<lang>/src/scanner.c` over
   `semgrep-<wrapper>/src/scanner.c`.

3. **Re-apply** only those Semgrep extensions:
   - Append Semgrep `TokenType` values **immediately before** `NONE` (or
     whatever sentinel upstream uses), matching the order of any
     `externals: ($, previous) => previous.concat([...])` entries in
     `grammar.js`.
   - In `scan`, handle those symbols with the same lookahead semantics as
     before (e.g. Ruby's statement ellipsis peeks for newline/EOF **without
     consuming** the newline so `_line_break` still works).
   - Keep a short `// sgrep-ext:` marker on Semgrep-only blocks.

4. **Delete** `semgrep-<wrapper>/src/scanner.cc`.

5. **Force-track** the new scanner (`src/` is gitignored):
   ```
   git add -f lang/semgrep-grammars/src/semgrep-<wrapper>/src/scanner.c
   ```
   Stage the `.cc` deletion too. Do **not** commit — the outer propose harness
   commits.

6. **Do not** change `prep` executability, inherited corpus symlinks,
   `grammar.js` rule bodies, `lang/languages-*`, or the upstream submodule.
   `update-grammar` already moved version membership when the harness picked
   the new tree-sitter pin.

## Never edit

- `tree-sitter-<lang>/` (submodule)
- `lang/languages-*` / `language-variants-*` (harness/`update-grammar`)
- Semgrep corpus / `grammar.js` rule bodies (hand off to `fix-semgrep-grammar`)
- CST→AST / OCaml / proprietary repos

## Exit contract

Print one line:

- **`MIGRATE-SEMGREP-SCANNER: SUCCESS`** — wrapper has force-staged `scanner.c`,
  no `scanner.cc`, Semgrep extensions re-applied; summarize the delta.
- **`MIGRATE-SEMGREP-SCANNER: CANNOT_PROCEED`** — upstream still C++, or Semgrep
  extensions cannot be expressed in the new scanner; state the blocker.
- **`MIGRATE-SEMGREP-SCANNER: FAILED`** — unexpected error; include the error.

Do not commit, push, or open a PR.
