/*
  semgrep-elixir

  Extends the standard elixir grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-elixir/grammar');

module.exports = grammar(base_grammar, {
  name: 'elixir',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // No need for _SEMGREP_EXPRESSION hack here, because Elixir allows
    // toplevel expressions.
      
    // Metavariables
    identifier: ($, previous) => {
      return choice(
        previous,
        $._semgrep_metavariable
      );
    },

    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

    // Ellipsis
    // No need for extensions to _expressions for ellipsis because
    // Elixir already uses "..." as valid identifiers
      
    _expression: ($, previous) => choice(
      ...previous.members,
      $.deep_ellipsis,
    ),
      
    // The actual ellipsis rules
    deep_ellipsis: $ => seq(
            '<...', $._expression, '...>'
    ),
  }
});
