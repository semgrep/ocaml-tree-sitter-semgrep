/*
  semgrep-dart

  Extends the standard dart grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-dart/grammar');

module.exports = grammar(base_grammar, {
  name: 'dart',

  conflicts: ($, previous) => previous.concat([
    [$._expression, $.formal_parameter],
    [$.spread_element, $.semgrep_ellipsis],
    [$._expression, $.expression_statement],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     No need for special extensions for metavariables because Dart
     already accepts $ as part of an identifier.
  */
  rules: {
    semgrep_ellipsis: $ => '...',
    deep_ellipsis: $ => seq(
            '<...', $._expression, '...>'
    ),

    _expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.deep_ellipsis,
    ),
    expression_statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),
    formal_parameter: ($, previous) => choice(
       $.semgrep_ellipsis,
       previous
    ),
}
});
