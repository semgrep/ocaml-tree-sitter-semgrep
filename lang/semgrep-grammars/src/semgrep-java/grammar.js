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

    // We need to add semgrep_ellipsis to the statement rule, so that the
    // semgrep ellipsis by itself, without a semicolon, is considered a valid
    // statement, e.g. for:
    //
    // foo();
    // ...
    // bar();
    //
    // However, it also needs to be a valid expression. So, there is a conflict
    // here, but it should be adequately resolved by allowing tree sitter to
    // explore both options with GLR. It's probably not a true ambiguity, just
    // an LR(1) conflict. However, even if it is, it should be an innocuous one.
    [$.primary_expression, $.statement],
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

    statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    formal_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),
  }
});
