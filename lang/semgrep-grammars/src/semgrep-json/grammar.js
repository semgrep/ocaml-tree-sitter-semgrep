/*
  semgrep-json

  Extends the standard json grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-json/grammar');

module.exports = grammar(base_grammar, {
  name: 'json',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    document: ($, previous) => choice(
      previous,
      seq($.pair, optional(','))
    ),

    // Need high precedence so this is preferred over global_variable.
    semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

    semgrep_ellipsis: $ => '...',

    object: $ => seq(
      '{', commaSep($.pair), optional(','), '}',
    ),

    string: ($, previous) => choice(
      previous,
      $.semgrep_metavariable,
    ),

    _value: ($, previous) => prec(1, choice(
      previous,
      $.semgrep_ellipsis,
    )),

    pair: ($, previous) => choice(
      previous,
      seq($.semgrep_ellipsis)
    ),

  /*

    _expression: ($, previous) => choice(
      $.semgrep_ellipsis,
      ...previous.members
    ),
  */
  }
});

/**
 * Creates a rule to match one or more of the rules separated by a comma
 *
 * @param {RuleOrLiteral} rule
 *
 * @returns {SeqRule}
 */
function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}

/**
 * Creates a rule to optionally match one or more of the rules separated by a comma
 *
 * @param {RuleOrLiteral} rule
 *
 * @returns {ChoiceRule}
 */
function commaSep(rule) {
  return optional(commaSep1(rule));
}