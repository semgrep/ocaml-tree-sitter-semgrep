/*
  semgrep-php

  Extends the standard php grammar with semgrep pattern constructs.

  Notes on the lexer interaction with PHP variables:
  - PHP variables natively start with `$` (e.g. `$foo`), so a metavariable
    such as `$FOO` already parses as a `variable_name`. We do NOT need to
    introduce a separate metavariable-as-variable token.
  - For metavariables in identifier positions (class names, function names,
    type names, etc.) we use `semgrep_metavar_ident`, a token that looks like
    `$FOO` but matches uppercase metavariable convention. Since `$FOO` would
    otherwise lex as `$` + `name`, we use a higher-precedence token. In
    identifier positions a `variable_name` is not legal, so there is no
    ambiguity.
  - PHP's variable-variable syntax `$$F` lexes naturally as `$` + `$F`, where
    `$F` is a `variable_name`. We rely on `semgrep_metavar_ident` only being
    accepted in identifier positions, not variable positions, so `$$FOO` keeps
    its variable-variable meaning.
*/

const base_grammar = require('tree-sitter-php/grammar');

module.exports = grammar(base_grammar, {
  name: 'php',

  conflicts: ($, previous) => previous.concat([
    // semgrep_ellipsis as expression vs as statement: a bare `...` can be
    // either an `expression_statement` (when followed by `;`) or a
    // standalone `semgrep_ellipsis` statement.
    [$._expression, $.program],
    [$._expression, $.compound_statement],
    [$._expression, $.while_statement],
    [$._expression, $.if_statement],
    [$._expression, $.foreach_statement],
    [$._expression, $.else_clause],
    [$._expression, $.else_if_clause],
    [$._expression, $.colon_block],
    [$._expression, $.default_statement],
    [$._expression, $.declare_statement],
    [$._expression, $.match_block],
    [$._expression, $.for_statement],
  ]),

  rules: {
    /*
       Semgrep tokens
    */

    // A bare ellipsis. PHP already uses `...` for variadic parameters and
    // unpacking; we keep those rules untouched and prefer the native
    // interpretations by giving `semgrep_ellipsis` a negative precedence.
    semgrep_ellipsis: $ => prec(-1, '...'),

    // `<... expr ...>` - matches an expression "deeply" inside another.
    semgrep_deep_ellipsis: $ => seq('<...', $._expression, '...>'),

    // `$...ARGS` - matches a sequence of arguments / parameters.
    semgrep_variadic_metavariable: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*/,

    // `$FOO` used in identifier positions (class / function / type / attribute
    // name). This is given a higher token precedence than the default
    // `$` + `name` decomposition so it lexes as a single token, but it is only
    // accepted in places where an identifier (not a variable) is expected, so
    // it does not collide with `variable_name`.
    semgrep_metavar_ident: $ => token(prec(1, /\$[A-Z_][A-Z_0-9]*/)),

    // Convenience: a `name` or a metavariable used as an identifier.
    _semgrep_extended_name: $ => choice($.name, $.semgrep_metavar_ident),

    /*
       Wire ellipsis into expression and statement positions
    */

    _expression: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_deep_ellipsis,
    ),

    _statement: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Allow `...` inside class / interface / trait bodies.
    _member_declaration: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Allow `...` inside enum bodies.
    _enum_member_declaration: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // Allow `...` and `$...ARGS` as a parameter.
    formal_parameters: $ => seq(
      '(',
      commaSep(choice(
        $.simple_parameter,
        $.variadic_parameter,
        $.property_promotion_parameter,
        $.semgrep_ellipsis,
        $.semgrep_variadic_metavariable,
      )),
      optional(','),
      ')'
    ),

    // Allow `$...ARGS` as a function-call argument. `...` (semgrep_ellipsis)
    // already matches inside expressions so it works as an argument too.
    argument: ($, previous) => choice(
      previous,
      $.semgrep_variadic_metavariable,
    ),

    // Allow `...` as a match arm. We use `prec.dynamic` to prefer treating a
    // standalone `...` as a top-level match arm rather than as the start of a
    // `match_condition_list`.
    match_block: $ => prec.left(seq(
      '{',
      commaSep1(choice(
        $.match_conditional_expression,
        $.match_default_expression,
        prec.dynamic(1, $.semgrep_ellipsis),
      )),
      optional(','),
      '}'
    )),

    // Allow ellipsis inside attribute argument lists. `arguments` is the
    // generic call-arguments rule, which is already covered above via
    // `argument` and the expression-level ellipsis. Nothing extra needed.

    /*
       Wire metavariable-as-identifier into name positions
    */

    class_declaration: $ => prec.right(seq(
      optional(field('attributes', $.attribute_list)),
      optional(field('modifier', choice($.final_modifier, $.abstract_modifier))),
      keyword('class'),
      field('name', $._semgrep_extended_name),
      optional($.base_clause),
      optional($.class_interface_clause),
      field('body', $.declaration_list),
      optional($._semicolon)
    )),

    interface_declaration: $ => seq(
      keyword('interface'),
      field('name', $._semgrep_extended_name),
      optional($.base_clause),
      field('body', $.declaration_list)
    ),

    trait_declaration: $ => seq(
      keyword('trait'),
      field('name', $._semgrep_extended_name),
      field('body', $.declaration_list)
    ),

    enum_declaration: $ => prec.right(seq(
      optional(field('attributes', $.attribute_list)),
      keyword('enum'),
      field('name', $._semgrep_extended_name),
      optional(seq(':', $._type)),
      optional($.class_interface_clause),
      field('body', $.enum_declaration_list)
    )),

    _function_definition_header: $ => seq(
      keyword('function'),
      optional('&'),
      field('name', choice(
        $.name,
        alias($._reserved_identifier, $.name),
        $.semgrep_metavar_ident,
      )),
      field('parameters', $.formal_parameters),
      optional($._return_type)
    ),

    // Type names (used in parameter types, return types, etc.).
    named_type: $ => choice(
      $.name,
      $.qualified_name,
      $.semgrep_metavar_ident,
    ),

    // `extends` / `implements`: allow metavar in the base list.
    base_clause: $ => seq(
      keyword('extends'),
      commaSep1(choice(
        $.name,
        alias($._reserved_identifier, $.name),
        $.qualified_name,
        $.semgrep_metavar_ident,
      ))
    ),

    class_interface_clause: $ => seq(
      keyword('implements'),
      commaSep1(choice(
        $.name,
        alias($._reserved_identifier, $.name),
        $.qualified_name,
        $.semgrep_metavar_ident,
      ))
    ),

    // Attribute names.
    attribute: $ => seq(
      choice(
        $.name,
        alias($._reserved_identifier, $.name),
        $.qualified_name,
        $.semgrep_metavar_ident,
      ),
      optional(field('parameters', $.arguments))
    ),
  }
});

function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}

function commaSep(rule) {
  return optional(commaSep1(rule));
}

// Mirrors the helper in tree-sitter-php's grammar.js so we can re-declare
// rules that use case-insensitive keywords.
function keyword(word, aliasAsWord = true) {
  let pattern = '';
  for (const letter of word) {
    pattern += `[${letter}${letter.toLocaleUpperCase()}]`;
  }
  let result = new RegExp(pattern);
  if (aliasAsWord) result = alias(result, word);
  return result;
}
