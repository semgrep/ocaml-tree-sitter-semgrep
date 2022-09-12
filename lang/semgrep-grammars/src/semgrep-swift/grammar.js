/*
  semgrep-swift

  Extends the standard swift grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-swift/grammar');

module.exports = grammar(base_grammar, {
  name: 'swift',

  conflicts: ($, previous) => previous.concat([
    [$._three_dot_operator, $.semgrep_expression_ellipsis],
    [$._three_dot_operator, $.semgrep_expression_ellipsis, $.semgrep_ellipsis],
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
    semgrep_expression_ellipsis: $ => prec.dynamic(-1337, "..."),

    // Use "..." here and in semgrep_expression_ellipsis above, rather than
    // `$._three_dot_operator`, so that the conflicts list is easier to
    // understand.
    semgrep_ellipsis: $ => "...",

    semgrep_deep_ellipsis: $ => seq("<...", $._expression, $.custom_operator),

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
  }
});
