/*
  semgrep-scala

  Extends the standard scala grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-scala-r2c/grammar');

module.exports = grammar(base_grammar, {
  name: 'scalar2c',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
  /*
    semgrep_ellipsis: $ => '...',

    _expression: ($, previous) => {
      return choice(
        $.semgrep_ellipsis,
        ...previous.members
      );
    }
  */
  }
});
