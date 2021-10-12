/*
  semgrep-bash

  Extends the standard bash grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-bash/grammar');

module.exports = grammar(base_grammar, {
  name: 'bash',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {

    // A variable name *not* followed by '=' or '+='.
    //
    _simple_variable_name: ($, previous) => choice(
      $.semgrep_metavariable,
      previous
    ),

    // An item in a command line, subject to expansion into multiple elements,
    // such as
    // - hello
    // - "$x".z
    // - $args
    // - 'hello world'
    // - $(ls)
    // etc.
    //
    _literal: ($, previous) => {
      return choice(
        $.semgrep_ellipsis,
        ...previous.members
      );
    },

    // We only want to extend simple variable names, not fragments of
    // command-line arguments. See 'literal'.
    _extended_word: $ => choice(
      $.semgrep_metavariable,
      $.word
    ),

    // Fragile. Copy of the original with $.word -> $._extended_word
    function_definition: $ => seq(
      choice(
        seq(
          'function',
          field('name', $._extended_word),
          optional(seq('(', ')'))
        ),
        seq(
          field('name', $.word),
          '(', ')'
        )
      ),
      field(
        'body',
        choice(
          $.compound_statement,
          $.subshell,
          $.test_command)
      )
    ),

    // ${X} etc.
    // The point of supporting an ellipsis here is to detect unquoted
    // expansions such as ${X} because "${X}" is usually what the programmer
    // wants. The variable inside the expansion can also be captured
    // using a metavariable:
    // - ${HOME#/} expands the HOME variable and removes the leading '/'.
    // - The pattern ${...} will match the whole $HOME, ${HOME}, and ${HOME#/}.
    // - The pattern ${$X} will match only the variable name 'HOME' in $HOME,
    //   ${HOME}, and ${HOME#/}.
    // - The pattern ${$X#/} is strictly more specific than ${$X} as it matches
    //   ${HOME#/} but not ${HOME} or ${HOME%/}.
    //
    expansion: ($, previous) => choice(
      seq('${', $.semgrep_ellipsis, '}'),
      previous
    ),

    semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,
    semgrep_ellipsis: $ => '...',
  }
});
