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

    // This is from permitting typed metavars to exist
    [$._type, $.formal_parameter, $.receiver_parameter],
    [$.annotated_type, $.receiver_parameter],

    [$.primary_expression, $.element_value_pair],
  ]),

  rules: {
    // Additional rules for constructs that are not, by themselves, valid Java
    // programs, but which should be valid Semgrep patterns.
    program: ($, previous) => choice(
      previous,
      $.constructor_declaration,
      $.expression,
      $.partials,
      prec(1, $.typed_metavariable_declaration),
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

    // This looks like `(Saxonreader $READER) = ...;`
    // This isn't real Java code, but I have observed that many Semgrep rules
    // take this form. It seems that this is something the old Menhir parser allowed,
    // and perhaps it's easier for the jsonnet rule generation pipeline to write
    // patterns in this way.
    // Regardless, it seems the easiest thing to do is to support this behavior.
    // Unfortunately, there's a lot of different kinds of declarations, so it is
    // hard to go to all the relevant nonterminals and patch them, but we can allow
    // the 98% case here.
    typed_metavariable_declaration: $ => prec.right(seq(
      '(',
      $._type,
      $.identifier,
      ')',
      '=',
      $.expression,
      ';'
    )),

    statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_named_ellipsis,
      $.typed_metavariable_declaration
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

    element_value_pair: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
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
       $.annotation,
    ),

    semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),
    deep_ellipsis: $ => seq('<...', $.expression, '...>'),

    typed_metavariable: $ => seq(
      '(',
       $._type,
       $.identifier,
       ')'
    ),

    // partial of method_declaration
    partial_method: $ => seq(
      optional($.modifiers),
      $._method_header
    ),
  }
});
