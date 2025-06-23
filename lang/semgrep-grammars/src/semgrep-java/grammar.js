/*
  semgrep-java

  Extends the standard java grammar with semgrep pattern constructs.
  Note that '$' is valid character in Java identifiers so we don't
  need to extend the grammar to support metavariables such as '$FOO'.
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

    [$._type, $.formal_parameter, $.receiver_parameter],
    [$.annotated_type, $.receiver_parameter],
  ]),

  rules: {
    // Additional rules for constructs that are not, by themselves, valid Java
    // programs, but which should be valid Semgrep patterns.
    program: ($, previous) => choice(
      previous,
      $.constructor_declaration,
      $.expression,
      $.partials,
    ),

    semgrep_ellipsis: $ => '...',
    semgrep_named_ellipsis: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*/,

    primary_expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_named_ellipsis,
      $.typed_metavariable,
      $.deep_ellipsis,
    ),

    statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_named_ellipsis
    ),

    field_access: $ => seq(
      field('object', choice($.primary_expression, $.super)),
      optional(seq(
        '.',
        $.super,
      )),
      '.',
      field('field', choice($.identifier, $._reserved_identifier, $.this, '...')),
    ),


    formal_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_named_ellipsis
    ),

    _class_body_declaration: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_named_ellipsis
    ),

    partials: $ => choice(
       $.partial_method,
    ),

    semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),
    deep_ellipsis: $ => seq('<...', $.expression, '...>'),

    typed_metavariable: $ => prec(1000, seq(
      '(',
       $._type,
       $.identifier,
       ')'
    )),

    // partial of method_declaration
    partial_method: $ => seq(
      optional($.modifiers),
      $._method_header
    ),
  }
});
