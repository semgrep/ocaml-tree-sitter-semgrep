/*
  semgrep-go

  Extends the standard go grammar with semgrep pattern constructs:
    - '...'           ellipsis
    - '$X'            metavariable
    - '$...X'         ellipsis-metavariable
    - '<... e ...>'   deep ellipsis

  Go identifiers cannot contain '$', so we introduce an explicit
  semgrep_metavariable token (similar to how semgrep-kotlin overrides
  simple_identifier).
*/

const base_grammar = require('tree-sitter-go/grammar');

module.exports = grammar(base_grammar, {
  name: 'go',

  conflicts: ($, previous) => previous.concat([
    // Allow GLR exploration when '...' could parse as either an
    // expression-position ellipsis or a statement-position ellipsis.
    [$._expression, $._statement],
    // 'Foo{...}' — '...' could be an expression literal_element or
    // the explicit ellipsis literal_element alternative.
    [$._expression, $.literal_element],
  ]),

  rules: {
    semgrep_ellipsis: $ => '...',
    semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),
    semgrep_ellipsis_metavar: $ => token(/\$\.\.\.[A-Z_][A-Z_0-9]*/),
    semgrep_deep_expression: $ => seq('<...', $._expression, '...>'),

    // Allow '$X', '...', '$...X', '<... e ...>' anywhere an expression
    // is allowed. Covers '$F(...)', '$OBJ.$M(...)', etc.
    _expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_metavariable,
      $.semgrep_ellipsis_metavar,
      $.semgrep_deep_expression,
    ),

    // Allow a bare '...' or '$...X' between statements.
    _statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_ellipsis_metavar,
    ),

    // 'func $F($X int, ...)' — accept '...', '$...REST', or a typed
    // metavariable parameter ('$X int'), in addition to upstream forms.
    parameter_declaration: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_ellipsis_metavar,
      seq(
        field('name', $.semgrep_metavariable),
        field('type', $._type),
      ),
    ),

    // Composite-literal bodies: 'Foo{$X: $Y, ...}', 'map[string]$T{...}',
    // '[]$T{ $X, ..., $Y }'.
    literal_element: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Struct bodies: 'struct { $F $T; ... }'.
    field_declaration: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Interface bodies: 'interface { $M(...) $T; ... }'.
    method_spec: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Selector field and struct field name: '$OBJ.$M(...)',
    // 'struct { $F int }'. _field_identifier is an alias of identifier
    // upstream; override it to also accept a metavariable.
    _field_identifier: $ => choice(
      alias($.identifier, $.field_identifier),
      $.semgrep_metavariable,
    ),

    // Type metavariable: 'map[string]$T', '[]$T', etc.
    _type_identifier: $ => choice(
      alias($.identifier, $.type_identifier),
      $.semgrep_metavariable,
    ),

    // Disambiguate '[...]T' (implicit-length array) from
    // '[' semgrep_ellipsis ']' indexing.
    implicit_length_array_type: $ => prec(1, seq(
      '[',
      '...',
      ']',
      field('element', $._type),
    )),

    // 'func $F(...)' — allow a metavariable as the function name.
    function_declaration: $ => prec.right(1, seq(
      'func',
      field('name', choice($.identifier, $.semgrep_metavariable)),
      field('type_parameters', optional($.type_parameter_list)),
      field('parameters', $.parameter_list),
      field('result', optional(choice($.parameter_list, $._simple_type))),
      field('body', optional($.block)),
    )),
  }
});
