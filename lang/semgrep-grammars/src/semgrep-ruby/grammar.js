/*
  semgrep-ruby

  Extends the standard ruby grammar with semgrep pattern constructs.
*/

const standard_grammar = require('tree-sitter-ruby/grammar');

module.exports = grammar(standard_grammar, {
  name: 'ruby',

  rules: {
    /* Ruby global variables start with a '$' ('global_variable'). */

    /* Alternative "entry point". Allows parsing a standalone expression. */
    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $._expression),

    /* Entry point. */
    program: ($, previous) => {
      return choice(
        previous,
        $.semgrep_expression
      );
    },

    /* We don't do anything special to distiguish metavariables, we just let them
       be parsed as global variables. Semgrep can fix that when converting to the
       Generic AST. */

    semgrep_ellipsis: $ => '...',

    semgrep_deep_ellipsis: $ => seq(
      '<...'
      , $._expression, '...>'
    ),

    _primary: ($, previous) => {
      return choice(
        ...previous.members,
        $.semgrep_ellipsis,
        $.semgrep_deep_ellipsis
      )
    },

    _simple_formal_parameter: ($, previous) => {
      return choice(
        ...previous.members,
        $.semgrep_ellipsis
      )
    },

    _method_name: ($, previous) => {
      return choice(
        ...previous.members,
        $.semgrep_ellipsis
      )
    }

  }
});
