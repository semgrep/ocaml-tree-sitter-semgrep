/*
  semgrep-python

  Extends the standard python grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-python/grammar');

// commaSep1 is defined in the base grammar's module scope and is therefore not
// visible here, so we redefine it for the argument_list override below.
function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}

module.exports = grammar(base_grammar, {
  name: 'python',

  conflicts: ($, previous) => previous.concat([
    // '{ ... }' is ambiguous between a set whose element is the '...' ellipsis
    // expression and a dictionary whose element is the '...' sgrep ellipsis.
    [$.primary_expression, $.dictionary],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
  /*
    semgrep_ellipsis: $ => '...',

    _expression: ($, previous) => choice(
      $.semgrep_ellipsis,
      ...previous.members
    ),
  */
    // Metavariables

   // Rather than creating a separate metavariable term
   // and adding it to identifiers, this instead overrides the
   // regex that is defined in the original tree-sitter grammar.
   // this is needed since currently in the original tree-sitter grammar,
   // identifier is a terminal, and thus can't do
   // the usual choice/previous shadowing definition.

    // The first alternative matches semgrep metavariable-ellipsis '$...NAME'
    // (e.g. '$...ARGS'). Like the menhir lexer, we treat it as just another
    // identifier (-> Name in the AST), so no extra conversion is needed.
    // The second alternative is the base identifier plus a leading '$' for
    // ordinary metavariables ('$FOO').
    identifier: $ =>
      /\$\.\.\.[A-Z_][A-Z_0-9]*|\$?[_\p{XID_Start}][_\p{XID_Continue}]*/,

    // Allow '...' in the attribute position of a dot-access expression,
    // so that patterns like `a. ... .d` work for matching call chains.
    // This mirrors the Java grammar's field_access override.
    // PREC.call = 22 in the base Python grammar.
    attribute: $ => prec(22, seq(
      field('object', $.primary_expression),
      '.',
      field('attribute', choice($.identifier, '...')),
    )),

    // sgrep-ext: deep ellipsis '<... e ...>' (menhir AST: DeepEllipsis).
    // Exposed as an expression, mirroring how the base grammar exposes
    // 'ellipsis' inside primary_expression.
    deep_ellipsis: $ => seq('<...', $.expression, '...>'),

    // Restated wholesale (rather than `choice(previous, ...)`) so the new
    // member is added to the *flat* choice. Using `previous` would wrap the
    // original members under a single nested node and churn every site in the
    // conversion that destructures a primary_expression.
    primary_expression: $ => choice(
      $.await,
      $.binary_operator,
      $.identifier,
      $.keyword_identifier,
      $.string,
      $.concatenated_string,
      $.integer,
      $.float,
      $.true,
      $.false,
      $.none,
      $.unary_operator,
      $.attribute,
      $.subscript,
      $.call,
      $.list,
      $.list_comprehension,
      $.dictionary,
      $.dictionary_comprehension,
      $.set,
      $.set_comprehension,
      $.tuple,
      $.parenthesized_expression,
      $.generator_expression,
      $.ellipsis,
      alias($.list_splat_pattern, $.list_splat),
      $.deep_ellipsis,
    ),

    // sgrep-ext: typed metavariable '$X: type' (menhir AST: TypedMetavar).
    // The menhir parser only accepts this in argument position to avoid
    // conflicts with annotations/slices/lambda elsewhere, so we do the same.
    typed_metavariable: $ => seq($.identifier, ':', $.type),

    // Copy of the base argument_list with $.typed_metavariable added to the
    // set of permitted arguments. (tree-sitter rule overrides replace the rule
    // wholesale, so the seq must be restated.)
    argument_list: $ => seq(
      '(',
      optional(commaSep1(
        choice(
          $.expression,
          $.list_splat,
          $.dictionary_splat,
          alias($.parenthesized_list_splat, $.parenthesized_expression),
          $.keyword_argument,
          $.typed_metavariable,
        ),
      )),
      optional(','),
      ')',
    ),

    // sgrep-ext: bare '...' as a parameter, e.g. 'def f(...)'
    // (menhir AST: ParamEllipsis). Restated flat (see primary_expression note).
    parameter: $ => choice(
      $.identifier,
      $.typed_parameter,
      $.default_parameter,
      $.typed_default_parameter,
      $.list_splat_pattern,
      $.tuple_pattern,
      $.keyword_separator,
      $.positional_separator,
      $.dictionary_splat_pattern,
      $.ellipsis,
    ),

    // sgrep-ext: a standalone decorator as a whole pattern, e.g. '@$NAME(...)'
    // (menhir AST: the 'Decorator' any). A lone decorator is not a valid
    // statement, so we let the module itself be a single decorator; the
    // conversion's parse_pattern turns that into a Decorator. A real program
    // (including a normal decorated definition) still uses the statement-list
    // form, which consumes the whole input and therefore wins.
    module: ($, previous) => choice(previous, $.decorator),

    // sgrep-ext: '...' as a dict element, e.g. '{ ..., $K: $V, ... }'
    // (menhir AST: Key (Ellipsis ...)). Restated wholesale to add $.ellipsis
    // to the element choice. Sets/lists already accept '...' since their
    // elements are plain expressions.
    dictionary: $ => seq(
      '{',
      optional(commaSep1(choice($.pair, $.dictionary_splat, $.ellipsis))),
      optional(','),
      '}',
    ),

    // sgrep-ext: '...' as an assignment / for-in target, e.g. the 'for ...'
    // in '[... for ... in xs]'. The comprehension body already accepts '...'
    // because it is a plain expression. Restated flat (see primary_expression
    // note).
    pattern: $ => choice(
      $.identifier,
      $.keyword_identifier,
      $.subscript,
      $.attribute,
      $.list_splat_pattern,
      $.tuple_pattern,
      $.list_pattern,
      $.ellipsis,
    ),

  }
});
