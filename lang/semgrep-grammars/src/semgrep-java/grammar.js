/*
  semgrep-java

  Extends the standard java grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-java/grammar');

module.exports = grammar(base_grammar, {
  name: 'java',

  conflicts: ($, previous) => previous.concat([
    // Conflict due to the addition of semgrep ellipsis to both. Can occur in
    // switch bodies where you would need lookahead to disambiguate between a
    // switch_label where the expression is a lambda and a switch_rule. There
    // are already several conflicts in the original grammar to deal with this
    // case.
    [$.primary_expression, $.formal_parameter],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Additional rules for constructs that are not, by themselves, valid Java
    // programs, but which should be valid Semgrep patterns.
    program: ($, previous) => choice(
      previous,
      $.constructor_declaration,
      $.expression,
    ),

    semgrep_ellipsis: $ => '...',

    primary_expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    formal_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),
  }
});
