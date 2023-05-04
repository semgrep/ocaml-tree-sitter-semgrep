/*
 * semgrep-rust
 *
 * Extend the original tree-sitter Rust grammar with semgrep-specific constructs
 * used to represent semgrep patterns.
 */

const standard_grammar = require("tree-sitter-cairo/grammar.js");

module.exports = grammar(standard_grammar, {
  name: "cairo",

  rules: {
    // Entry point
    source_file: ($, previous) => {
      return choice(previous, $.semgrep_expression, $.semgrep_statement);
    },

    _declaration: ($, previous) => {
      return choice(...previous.members, $.ellipsis);
    },

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: ($) => seq("__SEMGREP_EXPRESSION", $._expression),

    // Alternate "entry point". Allows parsing a standalone list of statements.
    semgrep_statement: ($) => seq("__SEMGREP_STATEMENT", repeat1($._statement)),

    // Metavariables
    semgrep_var: ($) => /\$[A-Z_][A-Z_0-9]*/,

    // Expression ellipsis
    _expression: ($, previous) => {
      return choice(
        ...previous.members,
        $.semgrep_var,
        $.ellipsis,
        $.deep_ellipsis
      );
    },

    member_declaration: ($, previous) => {
      return choice(previous, $.ellipsis);
    },

    deep_ellipsis: ($) => seq("<...", $._expression, "...>"),

    ellipsis: ($) => "...",
  },
});
