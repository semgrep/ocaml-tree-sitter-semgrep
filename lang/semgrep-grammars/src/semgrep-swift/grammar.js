/*
  semgrep-swift

  Extends the standard swift grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-swift/grammar');

module.exports = grammar(base_grammar, {
  name: 'swift',

  conflicts: ($, previous) => previous.concat([
    [$._three_dot_operator, $.semgrep_expression_ellipsis],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Swift has an unbounded range operator which is also three dots. When we
    // are parsing a pattern, we will convert that into an ellipsis after it's
    // parsed, but let's use low precedence here so that normally we only
    // produce this node where the unbounded range operator cannot exist.
    semgrep_expression_ellipsis: $ => prec.dynamic(-1337, $._three_dot_operator_custom),

    semgrep_ellipsis: $ => "...",

    semgrep_deep_ellipsis: $ => seq("<...", $._expression, "...>"),

    _expression: ($, previous) => choice(
      previous,
      $.semgrep_expression_ellipsis,
      $.semgrep_deep_ellipsis,
    ),

    _type: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    _type_level_declaration: ($, previous) => choice (
      previous, 
      $.semgrep_ellipsis,
    ),

    type_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Avoid problem with ocaml-tree-sitter due to $.multiline_comment
    // being an extra that can occur anywhere (like a comment) which is
    // removed from the CST.
    //_class_member_separator: ($) => choice($._semi, $.multiline_comment),
    _class_member_separator: ($) => $._semi,
  }
});
