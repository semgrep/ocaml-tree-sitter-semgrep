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
     ellipsis ('...') and metavariables ('$FOO') are actually
     valid HTML syntax in many places, so we don't need that many
     grammar extensions
  */
  rules: {
    //alt: redefine instead _start_tag_name and _end_tag_name?
    start_tag: ($, previous) => choice(
      $.semgrep_start_tag,
      previous
    ),
    end_tag: ($, previous) => choice(
      $.semgrep_end_tag,
      previous
    ),

    semgrep_start_tag: $ => seq(
      '<',
      $.semgrep_metavariable,
      repeat($.attribute),
      '>'
    ),

    semgrep_end_tag: $ => seq(
      '</',
      $.semgrep_metavariable,
      '>'
    ),

    semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),
      
  }
});
