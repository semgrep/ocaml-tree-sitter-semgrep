/*
  semgrep-sfapex

  Extends the standard sfapex grammar:
  - with semgrep pattern constructs ('$FOO', '...', ...)
  - with alternate entrypoints allowing simple code fragments to be parsed
    as semgrep patterns

  This work derives from what we have for Java in
  ../semgrep-java/grammar.js
*/

const base_grammar = require('tree-sitter-sfapex/apex/grammar');

module.exports = grammar(base_grammar, {
  name: 'apex',

  // See explanations in semgrep-java/grammar.js
  conflicts: ($, previous) => previous.concat([
    [$.primary_expression, $.formal_parameter],
    [$.primary_expression, $.statement],
  ]),

  rules: {
    // Entrypoint. We add alternate entrypoints for Semgrep patterns.
    parser_output: ($, previous) => choice(
      // Replace repeat($.declaration) which is too limited. (need to clarify)
      repeat($.statement),

      $.constructor_declaration,
      $.expression,
    ),

    semgrep_ellipsis: $ => '...',

    primary_expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    formal_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),
  }
});
