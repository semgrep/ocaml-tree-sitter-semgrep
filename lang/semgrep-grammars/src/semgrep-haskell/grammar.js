/*
  semgrep-haskell

  Extends the standard Haskell grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-haskell/grammar');

module.exports = grammar(base_grammar, {
  name: 'haskell',

  conflicts: ($, previous) => previous.concat([
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
  }
});
