# Semgrep construct name inventory

The semgrep pattern constructs the extension grammars add. Rule names vary per
language — this is the full family seen across the wrappers:

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
