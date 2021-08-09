/*
  semgrep-hack

  Extends the standard hack grammar with semgrep pattern constructs.
*/

// The npm package is 'tree-sitter-hacklang', not 'tree-sitter-hack',
// because npm doesn't like the word 'hack'. See original note in the
// project's readme.
//
const base_grammar = require('tree-sitter-hacklang/grammar');

module.exports = grammar(base_grammar, {
  name: 'hack',

  conflicts: ($, previous) => previous.concat([]),

  rules: {
    /*
      Support for semgrep ellipsis ('...')
    */

    // For now, we give precedence to native ellipsis (aka variadic modifiers).
    ellipsis: ($) => prec(-1, '...'),
    deep_ellipsis: ($) => prec(-1, seq('<...', $._expression, '...>')),

    // By using an empty statement, we leverage a statement type that is strictly only used within
    // $._statement and nowhere else.
    empty_statement: ($, previous) => {
      return choice(
        previous,
        // For conflict with `ellipsis;`
        // we want it to be read as an expression with a semicolon
        // instead of a statement
        prec(-1, $.ellipsis) // statement ellipsis
      );
    },

    _expression: ($, previous) => {
      return choice(previous, $.ellipsis, $.deep_ellipsis);
    },

    member_declarations: ($) => {
      return seq(
        '{',
        choice.rep(
          // Copied from existing grammar
          alias($._class_const_declaration, $.const_declaration),
          $.method_declaration,
          $.property_declaration,
          $.type_const_declaration,
          $.trait_use_clause,
          $.require_implements_clause,
          $.require_extends_clause,
          $.xhp_attribute_declaration,
          $.xhp_children_declaration,
          $.xhp_category_declaration,

          // Additions
          $.ellipsis
        ),
        '}'
      );
    },

    parameter: ($, previous) => {
      return choice(previous, $.ellipsis);
    },
  },
});
