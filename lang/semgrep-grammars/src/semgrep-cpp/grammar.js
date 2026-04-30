/*
  semgrep-cpp

  Extends the standard cpp grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-cpp/grammar');

module.exports = grammar(base_grammar, {
  name: 'cpp',

  conflicts: ($, previous) => previous.concat([
      // C++ allows 'sizeof ...(id)' hence the conflict
      [$.sizeof_expression, $.semgrep_ellipsis],
      // C allows ... in parameters
      [$.parameter_list, $.semgrep_ellipsis],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {

    // Entry point
    translation_unit: ($, previous) => choice(
      previous,
      $.semgrep_expression
    ),

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $._expression),

    // Typed metavariables

    // Token precedence so the lexer prefers `semgrep_metavar` over the
    // `identifier` rule (whose regex also accepts a leading `$`) when
    // the surrounding rule allows a metavar (e.g. inside an enum body).
    semgrep_metavar: $ => token(prec(1, /\$[A-Z_][A-Z_0-9]*/)),

    semgrep_typed_metavar: $ =>
      seq(
        $.type_descriptor,
        $.semgrep_metavar
      ),

    parenthesized_expression: ($, previous) => choice(
      previous,
      seq(
      '(',
      $.semgrep_typed_metavar,
      ')',
      )
    ),

    // Metavariables

    /* we can't use the usual:

	 identifier: ($, prev) => { return choice(prev, $._semgrep_metavariable);},
         _semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]* /,

      because in tree-sitter-c 'identifier' is used in the 'word:' directive and
      'identifier' then can't be a non-terminal. In other languages this is solved
      by having 'identifier' and a separate '_identifier_token' (e.g., in C#)
    */
    identifier: $ =>
      // derived by inserting an optional `$` in front of any identifier, as
      // defined in tree-sitter-c
      /\$?(\p{XID_Start}|_|\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8})(\p{XID_Continue}|\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8})*/,

    // Ellipsis

    _expression: ($, previous) => {
      return choice(
        previous,
        $.semgrep_ellipsis,
        $.deep_ellipsis,
        $.semgrep_named_ellipsis
      );
    },

    _block_item: ($, previous) => choice(
      previous,
      // We want to enable parsing something like
      // { ... }
      // so we need ... to be a valid block item.
      // We need a little bit of precedence so we prefer to reduce to
      // _block_item, as opposed to _expression, however.
      prec(1,$.semgrep_ellipsis)
    ),

    _top_level_statement: ($, previous) => choice(
      previous,
      // We also want to allow ... at the top level.
      prec(1,$.semgrep_ellipsis)
    ),

    // For method chaining, like foo. ... .bar()
    _field_identifier: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis
    ),

    // Allow `...` and `$X` inside class/struct bodies, e.g.
    //   class C { ... }
    //   struct S { $X }
    // The lexer prefers `semgrep_metavar` over `identifier` thanks to
    // the token precedence on `semgrep_metavar`, so a bare `$X` ends
    // up here rather than as a malformed field_declaration.
    _field_declaration_list_item: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_metavar
    ),

    // Allow `...` and `$X` inside enum bodies, e.g.
    //   enum E { ... }
    // The upstream rule is a `seq` so we must override it wholesale
    // (copied from tree-sitter-c with semgrep alternatives added).
    enumerator_list: $ => seq(
      '{',
      repeat(choice(
        seq($.enumerator, ','),
        alias($.preproc_if_in_enumerator_list, $.preproc_if),
        alias($.preproc_ifdef_in_enumerator_list, $.preproc_ifdef),
        seq($.preproc_call, ','),
        seq($.semgrep_ellipsis, ','),
        seq($.semgrep_metavar, ','),
      )),
      optional(choice(
        $.enumerator,
        alias($.preproc_if_in_enumerator_list_no_comma, $.preproc_if),
        alias($.preproc_ifdef_in_enumerator_list_no_comma, $.preproc_ifdef),
        $.preproc_call,
        $.semgrep_ellipsis,
        $.semgrep_metavar,
      )),
      '}',
    ),

    // Allow `operator $OP` as an operator name, e.g.
    //   T operator $OP(T x);
    operator_name: ($, previous) => choice(
      previous,
      prec(1, seq('operator', $.semgrep_metavar)),
    ),

    // So we prefer to parse a unary left fold for
    // 1 + ...
    // rather than the addition of an ellipsis
    _unary_left_fold: ($, previous) => prec(1, previous),

    // This is kind of messed up, but here's the idea.
    // Consider the following sequence:
    // ( <expr> +     ...
    //             ^ where we are here
    // This could be interpreted in two ways. We could choose to keep the `+`
    // as a verbatim `+`, which could potentially lead to parsing a binary
    // fold operator, which looks like:
    //   ( <expr> '+' '...' '+' <expr> )
    // or we could reduce the '+' into a _fold_operator, which could parse a
    // sequence like this:
    //   ( <expr> <_fold_operator> <expr> )
    // a priori, however, we don't know which choice to make! So the easiest
    // way is to permit the reduction in both cases, by making _binary_fold_operator
    // such that it can accept a _fold_operator, not a verbatim '+'.
    _binary_fold_operator: ($, previous) => seq(
      $._fold_operator, '...', $._fold_operator
    ),

    // Comma expressions like (e1, e2, e3) exist. But comma
    // is also a fold operator, meaning that a valid interpretation
    // of (1, ...) is as either a comma expression or a unary left
    // fold.
    _fold_operator: ($, previous) => prec(13, previous),

    semgrep_ellipsis: $ => '...',
    deep_ellipsis: $ => seq('<...', $._expression, '...>'),
    semgrep_named_ellipsis: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*/,

    // LANG-506: allow `for (...) <body>` as shorthand. The full header form
    // (with init/cond/update) already works because each component accepts
    // an _expression and ellipsis is an _expression.
    _for_statement_body: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),
  }
});
