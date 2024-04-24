/*
  semgrep-c

  Extends the standard c grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-c/grammar');

module.exports = grammar(base_grammar, {
  name: 'c',

  conflicts: ($, previous) => previous.concat([
    // This conflict arises from the case of
    // 'if' parenthesized_expression semgrep_ellipsis_metavar • '('  …
    // we don't know if we should reduce the whole if or just the metavar
    // not a very realistic case, so I don't care to fix this here
    [$.if_statement, $._expression]
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    semgrep_ellipsis: $ => '...',
    semgrep_deep_expression: $ => seq('<...', $._expression, '...>'),
    semgrep_typed_metavar: $ => seq('(', $.type_descriptor, $.semgrep_metavariable, ')'),
    semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,
    semgrep_ellipsis_metavar: $ => /\$\.\.\.[a-zA-Z_][a-zA-Z_0-9]*/,

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: ($) => seq("__SEMGREP_EXPRESSION", $._expression),

    _expression: ($, previous) => {
      return choice(
        $.semgrep_ellipsis,
        $.semgrep_deep_expression,
        $.semgrep_typed_metavar,
        $.semgrep_ellipsis_metavar,
        ...previous.members
      )
    },

    _statement: ($, previous) => {
      return choice(
        ...previous.members,
        // This needs to have a little more precedence, so that we can parse
        // { ... <stmts> }
        // properly, such that `...` is for the semgrep ellipsis.
        prec(1, $.semgrep_ellipsis),
        prec(1, $.semgrep_ellipsis_metavar),
      )
    },

    _top_level_statement: ($, previous) => {
      return choice(
        ...previous.members,
        prec(1, $.semgrep_ellipsis),
        prec(1, $.semgrep_ellipsis_metavar)
      )
    },

    _for_statement_body: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis
    ),

    _field_identifier: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_ellipsis_metavar
    ),

    // don't need to edit parameter_declaration because variadic_parameter already exists

    // Alternative entry point for pattern parsing
    translation_unit: ($, previous) => choice(
      previous,
      $.semgrep_expression
    )
  }
});
