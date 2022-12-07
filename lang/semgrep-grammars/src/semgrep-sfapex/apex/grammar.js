/*
  semgrep-sfapex

  Extends the standard sfapex grammar:
  - with semgrep pattern constructs ('$FOO', '...', ...)
  - with alternate entrypoints allowing simple code fragments to be parsed
    as semgrep patterns

  This work derives from what we have for Java in
  ../semgrep-java/grammar.js
*/

// Import utilities
const {
  ci,
  commaJoined,
  commaJoined1,
  joined,
} = require("tree-sitter-sfapex/common/common.js");

const base_grammar = require('tree-sitter-sfapex/apex/grammar');

module.exports = grammar(base_grammar, {
  name: 'apex',

  // See explanations in semgrep-java/grammar.js
  conflicts: ($, previous) => previous.concat([
    [$.primary_expression, $.formal_parameter],
    [$.primary_expression, $.statement],
  ]),

  rules: {
    // Entrypoint. We add alternate entrypoints for Semgrep patterns.
    parser_output: ($, previous) => choice(
      // Replace repeat($.declaration) which is too limited. (need to clarify)
      repeat($.statement),

      $.constructor_declaration,
      $.expression,

      ///// Partial definitions
      $._class_header,
      $._full_method_header,

      // Partial statements
/*
       | IF "(" expression ")" EOF { Partial (PartialIf ($1, $3)) }
       | TRY block             EOF { Partial (PartialTry ($1, $2)) }
       | catch_clause          EOF { Partial (PartialCatch $1) }
       | finally               EOF { Partial (PartialFinally $1) }
*/
    ),

    ///// Add Semgrep ellipsis (...) in several places
    semgrep_ellipsis: $ => '...',

    primary_expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    formal_parameter: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    ///// Add support for partial constructs used in Semgrep patterns

    // Redefine class_declaration, splitting it into header and body.
    class_declaration: ($) =>
      seq($._class_header, $.class_body),

    // Derived from the original class_declaration.
    // (hidden so that it doesn't change the original text expectations)
    _class_header: ($) => seq(
      optional($.modifiers),
      ci("class"),
      $.identifier,
      optional($.type_parameters),
      optional($.superclass),
      optional($.interfaces)
    ),

    // Derived from the original method_declaration.
    _full_method_header: ($) => seq(
      optional($.modifiers),
      $._method_header,
    ),
  }
});
