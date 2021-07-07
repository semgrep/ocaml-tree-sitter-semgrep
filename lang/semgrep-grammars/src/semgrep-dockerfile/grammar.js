/*
  semgrep-dockerfile

  Extends the standard dockerfile grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-dockerfile/grammar');

module.exports = grammar(base_grammar, {
  name: 'dockerfile',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {
    shell_fragment: ($, previous) => repeat1(
      choice(
        $.semgrep_ellipsis,
        $.semgrep_double_curly_metavariable,
        /[^\\\[\n#\s][^\\\n]*/,
        /\\[^\n]/
      )
    ),

    // Support ${{FOO}} as a metavariable, since it's unambiguous.
    // (experimental)
    semgrep_double_curly_metavariable: $ => seq(
      '${{',
      $.semgrep_metavariable_name,
      '}}'
    ),

    semgrep_metavariable_name: $ => /[A-Z_][A-Z_0-9]*/,
    semgrep_ellipsis: $ => '...',
  }
});
