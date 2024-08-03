/*
  semgrep-move-on-sui

  Extends the standard move grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-move-on-sui/grammar');
const _UNNARY_PREC = 10;
const UNARY_PREC = 13;
const FIELD_PREC = 14;
const CALL_PREC  = 15;


module.exports = grammar(base_grammar, {
  name: 'move_on_sui',
  
  conflicts: ($, previous) => previous.concat([
    [$.typed_metavariable, $.module_access],
    [$.module_body, $.block],
    [$.module_body ,$._expression_term],
    [$.module_body],
    [$._expression_term],
    [$.semgrep_statement,$._expression_term],
  ]),

  precedences: ($, previous) => previous.concat([
    [$.block_item, $.block, $.module_body, $.module_access],
    [$._expression_term, $.module_access],
    [$._bind, $.module_access],
    [$.block_identifier ,$.break_expression],
    [$.block_item, $._expression, $.module_access],
    [$.annotation_item, $.module_access],
    [$.module_access, $.field_access_ellipsis_expr],
    [$.bind_unpack, $.name_expression],
    [$.type_arguments, $._type, $.module_access],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Semgrep components, source: semgrep-rust
    ellipsis: $ => '...',
    deep_ellipsis: $ => seq('<...',$._expression, '...>'),
    _semgrep_metavar_ellipsis: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*/,
    _semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,


    // Typed metavariable (an expression, not a parameter)
    // This is grammatically indistinguishable from `$.type_hint_expr: $ => seq('(', $._expr, ':', $.type, ')')`.
    // This will be handled by the semgrep converter by checking the metavariable name (`$`).
    typed_metavariable: $ => seq('(', $.identifier, ':', $._type, ')'),

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: $ => choice(
      $._expression,
      $.let_statement,
    ),

    // Alternate "entry point". Allows parsing a standalone list of sequence items (statements).
    semgrep_statement: $ => repeat1(choice(
      $.block_item,
      $.use_declaration,
      $.friend_declaration,
      $.constant,
      $._function_item,
      $._struct_item,
      $._enum_item,
      $.spec_block,
      $.module_body
    )),

    // Alternate "entry point". Allows parsing partial declarations (signatures).
    semgrep_partial: $ => seq(
       choice(
        $._function_signature,
        $._struct_signature,
        $._enum_signature,
      )
    ),

    // Extend the source_file rule to allow semgrep constructs
    source_file: ($, previous) => choice(
      previous,
      $.semgrep_expression,
      $.semgrep_statement,
      $.semgrep_partial,
    ),

    // Module declaration
    module_body: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    module_access: ($, previous) => choice( 
      previous,
      $.ellipsis
    ),

    // Spec block members
    _spec_block_memeber: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // statement (block item)
    block_item: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // struct field annotations
    field_annotation: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // struct field bindings
    // (e.g. `let T { field_1, ... } = 0;`)
    bind_field: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // struct binding
    // (e.g. `let T { field_1, var: ..., } = obj;`)
    // (e.g. `let ... = obj;`)
    _bind: ($, previous) => choice(
      ...previous.members,
      $.ellipsis,
    ),

    // (e.g. `#[..., attr(...)]`)
    annotation_item: ($, previous) => choice(
      previous,
      $.ellipsis
    ),

    // use member
    // (e.g. `use module_ident::...;`, `use module_ident::{..., item_ident}`)
    use_member: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // expression term
    _expression_term: ($, previous) => choice(
      previous,
      $.ellipsis,
      $.deep_ellipsis,
    ),

    // expression 
    _expression: ($, previous) => choice(
      previous,
      $.ellipsis,
      $.deep_ellipsis,
    ),
    
    // unary expression 
    _unary_expression: ($, previous) => choice(
      previous,
      prec(UNARY_PREC, $.ellipsis),
      prec(UNARY_PREC, $.deep_ellipsis),
      prec(UNARY_PREC, $.field_access_ellipsis_expr),
      $.typed_metavariable,

    ),
    _dot_or_index_chain: ($, previous) => choice(
      previous,
      $.field_access_ellipsis_expr
    ),

    // function parameter
    // (e.g. `call( ..., arg, ...)`)
    function_parameter: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // type
    // (e.g. `call( ..., arg, ...)`)
     _type: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // abilities
    // (e.g. struct XXX has ..., YYY)
    ability: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // type parameter
    // (e.g. `Type<..., T>`)
    type_parameter: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    // type arguments
    // (e.g. `Type<..., T>`)
    type_arguments: ($, previous) => choice(
      previous,
      $.ellipsis,
      seq('<',$.ellipsis, '>'),
    ),
    // type
    // pack field
    // (e.g. `Pack { ..., field }`)
    exp_field: ($, previous) => choice(
      previous,
      $.ellipsis,
    ),

    newline: ($, previous) => choice(),

    field_access_ellipsis_expr: $ => prec.left(FIELD_PREC, seq(
      field('element', $._dot_or_index_chain), '.',$.ellipsis )),
    // identifier, extended to support metavariables
    identifier: ($, previous) => token(choice(
      previous,
      // Metavariables
      prec(200,alias(
        /\$[A-Z_][A-Z_0-9]*/,$.meta_var)), 
      prec(300,alias(
          /\$\.\.\.[A-Z_][A-Z_0-9]*/,$.metavar_ellipsis)), 
        
    )),
  }
});
