/*
  semgrep-circom

  Extends the standard circom grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-circom/grammar');

module.exports = grammar(base_grammar, {
  name: 'circom',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {

    source_file: ($, previous) => {
      return choice(
        previous,
        repeat1($._statement),
        $._expression,
      );
    },

    // Metavariables for pragma version
    circom_pragma_token: ($, previous) => {
      return choice(
        previous,
        seq(
          $._circom,
          $.identifier
        )
      )
    },
    
    _expression: ($, previous) => {
      return choice(
        previous,
        $.ellipsis,
        $.deep_ellipsis
      );
    },

    main_component_definition: ($, previous) => {
      return choice(
        previous,
        seq(
          'component',
          'main',
          optional($.main_component_public_signals),
          '=',
          field('value', choice($.ellipsis, $.deep_ellipsis)),
          $._semicolon
    
        ),
      )
    },

    _component_declaration: ($, previous) => {
      return choice(
        previous,
        seq(
          field('name', $.identifier),
          optional(field('type', $.array_type)),
          optional(seq(
            '=',
            field('value', choice($.ellipsis, $.deep_ellipsis))
          ))
        )
      )
    },

    expression_statement: ($, previous) => {
      return choice(
            previous,
            prec.right(100, seq($.ellipsis, ';')),  // expression ellipsis
            prec.right(100, $.ellipsis),  // statement ellipsis
      );
    },

    parameter: ($, previous) => {
      return choice(
         previous,
         $.ellipsis
      );
    },

    for_statement: ($, previous) => {
      return choice(
         previous,
         seq('for', '(', $.ellipsis, ')', $._statement)
      );
    },
  
    ellipsis: $ => '...',

    deep_ellipsis: $ => seq(
      '<...', $._expression, '...>'
    ),
  
  }
});
