/*
  semgrep-swift

  Extends the standard swift grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-swift/grammar');

module.exports = grammar(base_grammar, {
  name: 'swift',

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

    // Avoid problem with ocaml-tree-sitter due to $.multiline_comment
    // being an extra that can occur anywhere (like a comment) which is
    // removed from the CST.
    //_class_member_separator: ($) => choice($._semi, $.multiline_comment),
    _class_member_separator: ($) => $._semi,
  }
});
