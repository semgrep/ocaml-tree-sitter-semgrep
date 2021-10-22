/*
  semgrep-bash

  Extends the standard bash grammar with semgrep pattern constructs.

  This adds special treatment for semgrep metavariables.
  Semgrep ellipses are covered by the 'word' rule.
*/

const base_grammar = require('tree-sitter-bash/grammar');

module.exports = grammar(base_grammar, {
  name: 'bash',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {

    // A variable name *not* followed by '=' or '+='.
    //
    _simple_variable_name: ($, previous) => choice(
      $.semgrep_metavariable,
      previous
    ),

    // Override variable assignments to treat '$X=42' as an assignment rather
    // than an ordinary literal.
    variable_assignment: ($, previous) => choice(
      seq(
        // $FOO= or $FOO+=
        choice(
          $.semgrep_metavar_eq,
          $.semgrep_metavar_pluseq
        ),
        field('value', choice(
          $._literal,
          $.array,
          $._empty_value
        ))
      ),
      previous
    ),

    // We only want to extend simple variable names, not fragments of
    // command-line arguments. See 'literal'.
    _extended_word: $ => choice(
      $.semgrep_metavariable,
      $.word
    ),

    // Fragile. Copy of the original with $.word -> $._extended_word
    function_definition: $ => seq(
      choice(
        seq(
          'function',
          field('name', $._extended_word),
          optional(seq('(', ')'))
        ),
        seq(
          field('name', $.word),
          '(', ')'
        )
      ),
      field(
        'body',
        choice(
          $.compound_statement,
          $.subshell,
          $.test_command)
      )
    ),

    semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,
    semgrep_metavar_eq: $ => /\$[A-Z_][A-Z_0-9]*=/,
    semgrep_metavar_pluseq: $ => /\$[A-Z_][A-Z_0-9]*\+=/,
  }
});
