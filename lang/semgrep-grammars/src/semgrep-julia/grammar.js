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

    // Metavariables
    // We allow an identifier to be a simple metavariable regex, so that
    // we properly support metavariables.
    // Low precedence, so that we take less priority than parsing as
    // an interpolation expression. See the comments below.
    identifier: ($, previous) =>
      prec(1, choice(
        previous,
        /\$[A-Z][a-zA-Z0-9]*/,
      )),

    // ...But we also allow an interpolation expression to be a metavariable.
    // `interpolation_expression` is a superset of identifiers, so this doesn't
    // produce any extra parsing power, but we play with the precedence so that
    // anytime we see an interpolation_expression that is a metavariable, we
    // should prefer to parse it as an `interpolation_expression` rather than an
    // `identifier`.
    //
    // This ensures that in the produced parse tree, even if we are parsing a
    // Julia target rather than pattern, we can retain enough information to
    // parse interpolation expressions normally, and only opt-in to parsing them
    // as identifiers.
    //
    // Notably, we can't say that `interpolation_expression` should just be
    // `prec(999, previous)`, because the token stream is different. We should
    // be able to handle the same token lexed by the metavariable regex, so we
    // duplicate the regex here.
    interpolation_expression: ($, previous) => choice(
      previous,
      // We alias the included metavariable to an $.identifier so that the parse
      // tree stays the same.
      alias(prec(999, /\$[A-Z][a-zA-Z0-9]*/), $.identifier)
    ),

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
