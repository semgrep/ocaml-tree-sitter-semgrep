/*
  semgrep-c

  Extends the standard c grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-c/grammar');

module.exports = grammar(base_grammar, {
  name: 'c',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {

    // Entry point: allow parsing a standalone semgrep expression.
    translation_unit: ($, previous) => choice(
      previous,
      $.semgrep_expression
    ),

    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $._expression),

    // Typed metavariables: e.g. (int $X)
    semgrep_metavar: $ => /\$[A-Z_][A-Z_0-9]*/,

    semgrep_typed_metavar: $ => seq(
      $.type_descriptor,
      $.semgrep_metavar
    ),

    parenthesized_expression: ($, previous) => choice(
      previous,
      seq('(', $.semgrep_typed_metavar, ')')
    ),

    // Ellipsis variants
    semgrep_ellipsis: $ => '...',
    deep_ellipsis: $ => seq('<...', $._expression, '...>'),
    semgrep_named_ellipsis: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*/,

    _expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.deep_ellipsis,
      $.semgrep_named_ellipsis
    ),

    // Allow `{ ... }` to reduce to a block item rather than just an expression.
    _block_item: ($, previous) => choice(
      previous,
      prec(1, $.semgrep_ellipsis)
    ),

    // Allow `...` at the top level.
    _top_level_item: ($, previous) => choice(
      previous,
      prec(1, $.semgrep_ellipsis)
    ),

    // Allow `...` as a struct field, e.g. struct $S { $T $F; ... };
    _field_declaration_list_item: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis
    ),

    // For method chaining, e.g. foo. ... .bar()
    _field_identifier: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis
    ),
  }
});
