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

    // Metavariables
    identifier: ($, previous) => {
      return token(
        choice(
          previous,
          // We allow an identifier to be the same as an identifier, but prefixed
          // with a dollar sign.
          // We could use a more specific regular expression, which would match
          // metavariables more faithfully, but either:
          // 1) this would result in cases where we tokenize as an identifier or
          // an interpolation expression where we don't want to, depending on how
          // we set up the precedence.
          // 2) this causes tokenization issues with interpolation expression that
          // have prefixes which are metavariables, such as $Pack, which is parsed
          // as two tokens -- an identifier "$P" and an identifier "ack".

          // It's better to allow anything prefixed with a dollar sign to be an identifier,
          // then sort it out in generic translation.
          token.immediate(seq("$", previous))
        ));
    },

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
