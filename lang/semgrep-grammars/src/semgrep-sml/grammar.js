/*
  semgrep-sml

  Extends the standard sml grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-sml/grammar');

module.exports = grammar(base_grammar, {
  name: 'sml',

  conflicts: ($, previous) => previous.concat([
    [$.mrule, $._atpat]
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    semgrep_ellipsis: $ => '...',

    // As it turns out, $x parses as the application of `$` to an identifier.
    // We'll just allow it to parse like that, and then fix it in generic translation.

    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

    _alphaAlphaNumeric_ident: ($, previous) => choice(
      $._semgrep_metavariable,
      previous
    ),

    _dec_no_local: ($, previous) => choice(
      $.semgrep_ellipsis,
      previous
    ),

    _spec: ($, previous) => choice(
      $.semgrep_ellipsis,
      previous
    ),

    _atpat: ($, previous) => choice(
      $.semgrep_ellipsis,
      previous
    ),
    
    mrule: ($, previous) => choice(
      $.semgrep_ellipsis,
      previous
    )
  }
});
