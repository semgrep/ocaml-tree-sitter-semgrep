/*
  semgrep-hcl

  Extends the standard hcl grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-hcl/grammar');

module.exports = grammar(base_grammar, {
  name: 'hcl',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Entry point
    config_file: ($, previous) => {
      return choice(
        previous,
        $.semgrep_expression
      );
    },

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $.expression),


    // Metavariables
    identifier: ($, previous) => {
      return choice(
        previous,
        $._semgrep_metavariable
      );
    },

    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),


    // Ellipsis
    body: ($, previous) => repeat1(
      choice(
        $.attribute,
        $.block,
        $.semgrep_ellipsis,
      ),
     ),

    object_elem: ($, previous) => {
      return choice(
        previous,
        //TODO: $.semgrep_ellipsis, conflict right now
      );
    },

    _expr_term: ($, previous) => {
      return choice(
        previous,
        $.semgrep_ellipsis,
        $.deep_ellipsis
      );
    },

    semgrep_ellipsis: $ => '...',

    deep_ellipsis: $ => seq(
      '<...', $.expression, '...>'
    ),

  }
});
