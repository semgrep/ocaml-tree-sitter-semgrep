/*
  semgrep-html

  Extends the standard html grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-html/grammar');

module.exports = grammar(base_grammar, {
  name: 'html',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {

/* pad: not sure why, but this is simpler than patching element but
   it does not work. I get some 

       "The rule `start_tag` matches the empty string" tree-sitter

   error.

    start_tag: ($, previous) => {
      return choice(
       $.semgrep_start_tag,
       ...previous.members
      );
    },
*/
    element: ($, previous) => {
      return choice(
       $.semgrep_element,
       ...previous.members
      );
    },

    semgrep_element: $ => 
     seq(
       $._semgrep_start_tag,
       repeat($._node),
       $._semgrep_end_tag
     ),

    _semgrep_start_tag: $ => seq(
        '<',
        $._semgrep_metavariable,
        repeat($.attribute),
        '/>'
     ),
    _semgrep_end_tag: $ => seq(
     '</',
     $._semgrep_metavariable,
     '>'
   ),

    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

  /*
    semgrep_ellipsis: $ => '...',
  */
  }
});
