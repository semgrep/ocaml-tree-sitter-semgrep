/*
  semgrep-python

  Extends the standard python grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-python/grammar');

module.exports = grammar(base_grammar, {
  name: 'python',

  conflicts: ($, previous) => previous.concat([
    // `...` inside a dict literal is ambiguous between a
    // `semgrep_ellipsis` element (LANG-465) and an `ellipsis` that
    // would otherwise start a `pair` key. Real Semgrep patterns
    // never write `... :` as a key, but tree-sitter still needs an
    // explicit conflict declaration to resolve the lookahead.
    [$.ellipsis, $.semgrep_ellipsis],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Metavariables
    //
    // Rather than creating a separate metavariable term and adding it
    // to identifiers, this overrides the regex defined in the original
    // tree-sitter grammar. This is needed because in the upstream
    // grammar `identifier` is a terminal and cannot use the usual
    // choice/previous shadowing definition.
    identifier: $ => /\$?[_\p{XID_Start}][_\p{XID_Continue}]*/,

    // Allow '...' in the attribute position of a dot-access expression,
    // so that patterns like `a. ... .d` work for matching call chains.
    // PREC.call = 22 in the base Python grammar.
    attribute: $ => prec(22, seq(
      field('object', $.primary_expression),
      '.',
      field('attribute', choice($.identifier, '...')),
    )),

    // Shared semgrep ellipsis token. Used by parameter lists, match-case
    // pattern lists, and dictionary literals.
    semgrep_ellipsis: $ => '...',

    // Variadic metavariable (e.g. `$...ARGS`) used in argument lists.
    semgrep_ellipsis_metavar: $ => token(/\$\.\.\.[A-Z_][A-Z_0-9]*/),

    // LANG-460: allow `...` in a function's parameter list, so patterns
    // like `def $F(...): ...` parse cleanly.
    parameter: ($, previous) => choice(
      $.semgrep_ellipsis,
      ...previous.members,
    ),

    // LANG-461: accept `$...ARGS` as a primary expression. This makes
    // it usable through any rule that already takes an `expression`,
    // including `argument_list`.
    primary_expression: ($, previous) => choice(
      $.semgrep_ellipsis_metavar,
      $.typed_metavar,
      ...previous.members,
    ),

    // LANG-463: typed metavariable `($X : T)`. The leading identifier
    // must be a metavariable (start with `$`) to disambiguate from a
    // regular `parenthesized_expression`. We use a dynamic precedence
    // bump so the parser prefers `typed_metavar` whenever the inner
    // identifier is a metavariable.
    typed_metavar: $ => prec.dynamic(1, seq(
      '(',
      $.identifier,
      ':',
      field('type', $.type),
      ')',
    )),

    // LANG-464: allow `...` as a sub-pattern inside class/list/tuple/
    // dict patterns of a `match` statement. `case_pattern` is the
    // shared choice used by every pattern container, so a single
    // override lights up ellipsis everywhere.
    case_pattern: ($, previous) => prec(1, choice(
      $.semgrep_ellipsis,
      ...previous.content.members,
    )),

    // LANG-465: allow `...` as an element of a dict literal alongside
    // `pair` and `dictionary_splat`. The base rule is a `seq(...)`
    // not a `choice(...)`, so we restate it.
    dictionary: $ => seq(
      '{',
      optional(commaSep1(choice(
        $.pair,
        $.dictionary_splat,
        $.semgrep_ellipsis,
      ))),
      optional(','),
      '}',
    ),
  }
});

function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}
