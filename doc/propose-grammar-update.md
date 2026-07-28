# Propose grammar updates (`scripts/propose-grammar-update`)

Automated path for bumping an upstream `tree-sitter-<lang>` submodule to its
latest **stable** release tag, regenerating corpus snapshots, and optionally updating the `semgrep-<lang>` grammar and opening PRs.

Prefer this script (or the
[Propose grammar updates](../.github/workflows/propose-grammar-updates.yml)
workflow) over the manual [How to upgrade the grammar for a
language](https://semgrep.dev/docs/contributing/updating-a-grammar/) walkthrough
when you want a tag-pinned bump with snapshot regen and PR wiring.

`scripts/update-grammar` is deprecated. New work should go through `propose-grammar-update`.

## Prerequisites

- Repo built/installed as in the main README (`make setup`, `make && make install`).
- [`uv`](https://docs.astral.sh/uv/) (the script is a uv inline script).
- For `--open-pr` / `--release`: `gh` authenticated (`GH_TOKEN` / `GITHUB_TOKEN`).
- For `--language-agent`: `CURSOR_API_KEY` (and optionally `CURSOR_MODEL`).

## Common commands

All commands run as `uv run --script scripts/propose-grammar-update <args>`.

| Args | What it does |
|--|--|
| `--list-languages [--updatable-only] [--json]` | List proposable languages |
| `kotlin --resolve-tag-only` | Resolve the latest stable tag, no mutation |
| `kotlin` | Bump → regenerate corpus snapshots → `test-lang` → reset tree; prints one JSON result line on stdout |
| `kotlin --dry-run` | Full bump/test; shows the would-be PR, no push |
| `kotlin --open-pr` | Open a PR in this repo when the bump is green |
| `kotlin --open-pr --language-agent` | Same, dispatching the [`fix-semgrep-grammar`](fix-semgrep-grammar-skill.md) skill and re-testing on `test-lang` failure |
| `kotlin --release --result result-kotlin.json` | Release the validated parser to `semgrep-<lang>` (after the `grammar-update/<lang>/<tag>` branch exists here); pass the propose job's result artifact so the release matches what was tested |
| `--summarize results/` | Summarize many `result-*.json` artifacts (used by CI) |

## What a successful propose does

1. Picks the newest stable upstream tag this repo can build (ABI 14; respects
   C++ scanner / declared `tree-sitter-cli` constraints).
2. Bumps the submodule via `update-grammar --skip-release` and syncs
   `lang/languages-*` / `lang/language-variants-*`.
3. Regenerates corpus snapshots (`tree-sitter test --update`).
4. Runs `./test-lang <lang>` (authoritative pass/fail).
5. With `--open-pr`, commits on `grammar-update/<lang>/<tag>` and opens a PR
   against `GRAMMAR_BASE_BRANCH` (default `main`).

Stdout is a single JSON object (`status`: `updated`, `no-op`, `no-tags`,
`exists`, `failed`, or dry-run). Progress goes to stderr.

## CI

`.github/workflows/propose-grammar-updates.yml` enumerates languages, runs
propose per language (optional language agent), then integrates green bumps
with `--release`. Dispatch it from the Actions UI with a single language or
`all`.

## Environment

| Variable | Role |
|--|--|
| `GH_TOKEN` / `GITHUB_TOKEN` | `gh` for PRs / repo lookups |
| `CURSOR_API_KEY` | Required only with `--language-agent` |
| `CURSOR_MODEL` | Model for the language agent (default `auto`) |
| `GRAMMAR_BASE_BRANCH` | Base branch for grammar-update PRs (default `main`) |
| `GITHUB_ORG` | Org for `semgrep-<lang>` repos (default `semgrep`) |
