/*
  semgrep-bash

  Extends the standard bash grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-bash/grammar');

module.exports = grammar(base_grammar, {
  name: 'bash',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {

    simple_expansion: ($, previous) => {
      return choice(
        $.semgrep_double_curly_metavariable,
        previous
      )
    },

    _primary_expression: ($, previous) => {
      return choice(
        $.semgrep_ellipsis,
        ...previous.members
      );
    },

    // Support ${{FOO}} as a metavariable, since it's unambiguous.
    // (experimental)
    semgrep_double_curly_metavariable: $ => seq(
      '${{',
      $.semgrep_metavariable_name,
      '}}'
    ),

    semgrep_metavariable_name: $ => /[A-Z_][A-Z_0-9]*/,
    semgrep_ellipsis: $ => '...',
  }
});
