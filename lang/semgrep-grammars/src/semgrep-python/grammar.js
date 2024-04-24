/*
  semgrep-python

  Extends the standard python grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-python/grammar');

module.exports = grammar(base_grammar, {
  name: 'python',

  conflicts: ($, previous) => previous.concat([
    [$.expression, $.pair],
    [$.ellipsis, $.pair]
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
  /*
    semgrep_ellipsis: $ => '...',

    _expression: ($, previous) => choice(
      $.semgrep_ellipsis,
      ...previous.members
    ),
  */

    semgrep_deep_expression: $ => seq('<...', $.expression, '...>'),
    semgrep_typed_metavar: $ => seq('(', $.identifier, ':', $.type, ')'),
    semgrep_ellipsis_metavar: $ => /\$\.\.\.[a-zA-Z_][a-zA-Z_0-9]*/,

    expression: ($, previous) => choice(
      ...previous.members,
      $.semgrep_deep_expression,
      $.semgrep_typed_metavar,
      $.semgrep_ellipsis_metavar,
    ),

    _statement: ($, previous) => choice(
      ...previous.members,
      prec(1, $.semgrep_ellipsis_metavar),
    ),

    attribute: ($, previous) => choice(
      previous,
      // This precedence is hard-coded here because we cannot reference the PREC that
      // is used within the official tree-sitter-python grammar.
      // At the time of this update, PREC.call is 22.
      prec(22,seq(
        field('object', $.primary_expression),
        '.',
        field('attribute', choice('...', $.semgrep_ellipsis_metavar))
      ))
    ),

    parameter: ($, previous) => choice(
      previous,
      '...',
      $.semgrep_ellipsis_metavar
    ),

    pair: ($, previous) => choice(
      previous,
      '...',
      $.semgrep_ellipsis_metavar
    ),

    // Metavariables

    // Rather than creating a separate metavariable term
    // and adding it to identifiers, this instead overrides the
    // regex that is defined in the original tree-sitter grammar.
    // this is needed since currently in the original tree-sitter grammar,
    // identifier is a terminal, and thus can't do
    // the usual choice/previous shadowing definition.

    identifier: $ => /\$?[_\p{XID_Start}][_\p{XID_Continue}]*/,

  }
});
