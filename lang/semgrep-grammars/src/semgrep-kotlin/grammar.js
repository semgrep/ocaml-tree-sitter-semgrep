/*
 * semgrep-kotlin
 *
 * Extend the standard kotlin grammar with metavariable pattern constructs.
 * Ellipsis are in the kotlin grammar, so no need to extend for ellipsis.
 */

// INVARIATN: Make sure that you are merging any commits into the `semgrep`
// branch of `tree-sitter-kotlin`! This is because our version of
// `tree-sitter-kotlin` is forked from the original repository, and we
// want our branch to be kept separate.

const standard_grammar = require("tree-sitter-kotlin/grammar");

module.exports = grammar(standard_grammar, {
  name: "kotlin",

  rules: {
    // Entry point
    source_file: ($, previous) => {
      return choice(previous, $.semgrep_expression);
    },

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: ($) => seq("__SEMGREP_EXPRESSION", $._expression),

    semgrep_named_ellipsis: ($) => /\$\.\.\.[a-zA-Z_][a-zA-Z_0-9]*/,

    // Metavariables
    simple_identifier: ($, previous) => {
      return choice(previous, "constructor", /\$[a-zA-Z_][a-zA-Z_0-9]*/);
    },

    typed_metavar: ($) => seq("(", $.simple_identifier, ":", $._type, ")"),

    // Statement ellipsis: '...' not followed by ';'
    _expression: ($, previous) => {
      return choice(
        previous,
        $.ellipsis, // statement ellipsis
        $.deep_ellipsis,
        $.typed_metavar,
        $.semgrep_named_ellipsis,
      );
    },

    navigation_suffix: ($, previous) => {
      return choice(previous, seq($._member_access_operator, $.ellipsis));
    },

    _class_member_declaration: ($, previous) => {
      return choice(previous, $.ellipsis);
    },

    _function_value_parameter: ($, previous) => {
      return choice(previous, $.ellipsis);
    },

    class_parameter: ($, previous) => {
      return choice(previous, $.ellipsis);
    },

    // Allow single-line `class Foo { ... }` patterns. Without this,
    // a bare ellipsis between `{` and `}` fails because class members
    // require trailing `semis` (see LANG-476).
    class_body: ($, previous) => {
      return choice(previous, seq("{", $.ellipsis, "}"));
    },

    // Same as `class_body`, for `enum class E { ... }` (LANG-483).
    // Higher prec so `enum class E { ... }` resolves to the dedicated
    // single-line alternative rather than the multi-line form with a
    // single `enum_entry` of ellipsis.
    enum_class_body: ($, previous) => {
      return choice(previous, prec(1, seq("{", $.ellipsis, "}")));
    },

    // Allow `...` as a stand-alone enum entry, for multi-line forms
    // like `enum class E { A, B, ... }` (LANG-483).
    enum_entry: ($, previous) => {
      return choice(previous, $.ellipsis);
    },

    // Allow `...` as a `when` body entry: `when ($X) { ... }` (LANG-480).
    // Higher prec than `_expression`'s ellipsis so a bare `...` in a
    // `when` body parses as a stand-alone entry rather than the start
    // of an expression-form `when_condition`.
    when_entry: ($, previous) => {
      return choice(previous, prec(1, $.ellipsis));
    },

    deep_ellipsis: ($) => seq("<...", $._expression, "...>"),

    ellipsis: ($) => "...",
  },
});
