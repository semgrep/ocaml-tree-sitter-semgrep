/*
  semgrep-promql

  Extends the standard promql grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-promql/grammar');

module.exports = grammar(base_grammar, {
  name: 'promql',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {
    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

    metric_name: ($, previous) => choice(
      $._semgrep_metavariable,
      previous
    ),

    function_name: ($, previous) => choice(
      $._semgrep_metavariable,
      previous
    ),

    label_name: ($, previous) => choice(
      $._semgrep_metavariable,
      previous
    ),

    label_value: ($, previous) => choice(
      $._semgrep_metavariable,
      previous
    ),
  }
});
