/*
  semgrep-move-on-aptos

  Extends the standard move-on-aptos grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-move-on-aptos/grammar');

const FIELD_PREC = 14;

module.exports = grammar(base_grammar, {
  name: 'move_on_aptos',

  conflicts: ($, previous) => previous.concat([
    [$.quantifier, $._quantifier_directive],
    [$.var_name, $._bind],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Semgrep components, source: semgrep-rust
    ellipsis: $ => '...',
    deep_ellipsis: $ => seq('<...', $._expr, '...>'),
    typed_metavariable: $ => seq($.identifier, ':', $.type),

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $._expr),

    // Alternate "entry point". Allows parsing a standalone list of sequence items (statements).
    semgrep_statement: $ => seq('__SEMGREP_STATEMENT', repeat1($._sequence_item)),

    // Extend the source_file rule to allow semgrep constructs
    source_file: ($, previous) => choice(
      previous,
      $.semgrep_expression,
      $.semgrep_statement,
    ),

    // Module declaration
    declaration: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // Spec block members
    _spec_block_member: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // struct field annotations
    field_annot: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // struct field bindings
    // (e.g. `let T { field_1, ... } = 0;`)
    bind_field: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // attribute
    // (e.g. `#[..., attr(...)]`)
    attribute: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // use member
    // (e.g. `use module_ident::...;`, `use module_ident::{..., item_ident}`)
    _use_member: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // expression 
    _expr: ($, previous) => choice(
      ...previous.members,
      $.ellipsis,
      $.deep_ellipsis,
      $.field_access_ellipsis_expr,
    ),

    // type parameter
    // (e.g. `T: ..., U: ..., ...`)
    parameter: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // trailing field access
    // (e.g. `foo.bar().baz(). ...`)
    field_access_ellipsis_expr: $ => prec.left(FIELD_PREC, seq(
      field('element', $._dot_or_index_chain), '.', $.ellipsis,
    )),

    // identifier, extended to support metavariables
    identifier: ($, previous) => token(choice(
      previous,
      // Metavariables
      alias(choice(
        /\$[A-Z_][A-Z_0-9]*/,
        /\$\.\.\.[A-Z_][A-Z_0-9]*/,
      ), $.meta_var),
    )),
  }
});
