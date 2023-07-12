/*
  semgrep-julia

  Extends the standard julia grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-julia/grammar');

module.exports = grammar(base_grammar, {
  name: 'julia',

  conflicts: ($, previous) => previous.concat([
    [$.typed_parameter, $._expression],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    semgrep_ellipsis: $ => '...',

    catch_clause: $ => prec(1, seq(
      'catch',
      optional(choice($.identifier, alias($.semgrep_ellipsis, $.catch_ellipsis))),
      optional($._terminator),
      optional($._block),
    )),

    _expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    _statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    typed_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),
  }
});
