/*
  semgrep-promql

  Extends the standard promql grammar with semgrep pattern constructs.
*/

const base_grammar = require("tree-sitter-promql/grammar");

module.exports = grammar(base_grammar, {
  name: "promql",

  conflicts: ($, previous) =>
    previous.concat([
      [
        $.instant_vector_selector,
        $.range_vector_selector,
        $.string_literal,
        $.float_literal,
        $.metric_name,
      ],
    ]),

  rules: {
    _semgrep_metavariable: (_) => token(/\$[A-Z_][A-Z_0-9]*/),

    metric_name: ($, previous) => choice($._semgrep_metavariable, previous),
    function_name: ($, previous) => choice($._semgrep_metavariable, previous),
    label_name: ($, previous) => choice($._semgrep_metavariable, previous),
    label_value: ($, previous) => choice($._semgrep_metavariable, previous),
    string_literal: ($, previous) => choice($._semgrep_metavariable, previous),
    float_literal: ($, previous) => choice($._semgrep_metavariable, previous),
    instant_vector_selector: ($, previous) =>
      choice($._semgrep_metavariable, previous),
    range_vector_selector: ($, previous) =>
      choice($._semgrep_metavariable, previous),
  },
});
