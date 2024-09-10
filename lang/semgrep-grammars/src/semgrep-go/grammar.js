/*
  semgrep-go

  Extends the standard go grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-go/grammar');

module.exports = grammar(base_grammar, {
  name: 'go',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    semgrep_ellipsis: $ => "...",

    semgrep_ellipsis_metavar : $ => /\$\.\.\.[a-zA-Z_][a-zA-Z_0-9]*/,
    semgrep_deep_ellipsis: $ => seq("<...", $._expression, "...>"),

    // The parser tries to wrap ellipsis with expression statements since we
    // list ellipsis as expressions and usually we use them in a statement
    // position (i.e `if(true) {...}`)
    _statement: ($, previous) => choice(
      previous,
      prec(1,$.semgrep_ellipsis_metavar),
      prec(1,$.semgrep_deep_ellipsis),
      prec(1,$.semgrep_ellipsis)
    ),
 
    _expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis_metavar,
      $.semgrep_deep_ellipsis,
      $.semgrep_ellipsis,
      $.typed_metavar
    ),

    typed_metavar: $ => seq(
      "(", $.identifier, ":", $._type, ")"
    ),

    identifier: ($, previous) => token(choice(
      previous,
      // inline this here so we can stay inside of the `token`, because
      // `identifier` is the word token
      /\$[A-Z_][A-Z_0-9]*/
    )),

    parameter_declaration: ($, previous) => choice(
      $.semgrep_ellipsis,
      $.semgrep_ellipsis_metavar,
      previous
    ),

    // slightly more precedence so we bump this up over using `...`
    // for a semgrep ellipsis
    implicit_length_array_type: ($, previous) => prec(1, previous)
  }
});
