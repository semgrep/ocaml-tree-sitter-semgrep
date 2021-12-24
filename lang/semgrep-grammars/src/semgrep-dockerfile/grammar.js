/*
  semgrep-dockerfile

  Extends the standard dockerfile grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-dockerfile/grammar');

module.exports = grammar(base_grammar, {
  name: 'dockerfile',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {
    _instruction: ($, previous) => choice(
      $.semgrep_ellipsis,
      previous
    ),

    // overrides the original definition
    string_array: ($) =>
      seq(
        "[",
        optional(
          seq($._array_element, repeat(seq(",", $._array_element)))
        ),
        "]"
      ),

    _array_element: ($) => choice(
      $.double_quoted_string,
      $.semgrep_ellipsis,
      $.semgrep_metavariable
    ),

    // TODO: support metavariables and ellipses in a bunch of places
    semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,
    semgrep_ellipsis: $ => '...',
  }
});
