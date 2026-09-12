/*
  semgrep-scala

  Extends the standard Scala grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-scala/grammar');

module.exports = grammar(base_grammar, {
    name: 'scala',

    conflicts: ($, previous) => [
        ...previous,
        [$._simple_expression, $.semgrep_val_or_var_definition],
    ],

    rules: {
        semgrep_expression: $ => seq(token(prec(100, '__SEMGREP_EXPRESSION')), $.expression),
        semgrep_statement: $ => seq(token(prec(100, '__SEMGREP_STATEMENT')), choice($.expression, $._definition)),
        semgrep_member_decl: $ => seq(token(prec(100, '__SEMGREP_MEMBER_DECL')), choice($.function_definition, $.function_declaration, $.val_definition, $.val_declaration, $.var_definition, $.var_declaration)),
        // LANG-482: bare `case $X => ...` clauses outside a match block.
        semgrep_case_clause: $ => $.case_clause,
        semgrep_metavariable: _ => token(prec(1, /\$[A-Z][A-Za-z0-9_]*/)),
        semgrep_ellipsis: _ => token(prec(1, '...')),
        semgrep_ellipsis_metavariable: _ => token(prec(1, /\$\.\.\.[A-Za-z_][A-Za-z0-9_]*/)),
        deep_expression: $ => prec(10, seq('<...', $.expression, '...>')),

        _top_level_definition: ($, previous) => choice(
            $.semgrep_expression,
            $.semgrep_statement,
            $.semgrep_member_decl,
            $.semgrep_case_clause,
            previous,
        ),
        _simple_expression: ($, previous) => choice(
            previous,
            $.symbol_literal,
            $.semgrep_metavariable,
            $.deep_expression,
            $.semgrep_ellipsis_metavariable,
            $.semgrep_ellipsis,
        ),
        _pattern: ($, previous) => choice(previous, $.semgrep_ellipsis),
        parameter: ($, previous) => choice(previous, $.semgrep_ellipsis),
        class_parameter: ($, previous) => choice(previous, $.semgrep_ellipsis),
        enumerator: ($, previous) => choice(previous, prec(1, $.semgrep_ellipsis)),

        // LANG-488: allow `...` in place of (or interleaved with) case clauses
        // so patterns like `$X match { ... }` parse cleanly. The upstream
        // form (with at least one concrete `case_clause`) is kept verbatim so
        // existing tests that expect a trailing `...` to be absorbed into
        // the *body* of the last case_clause still parse that way. The new
        // ellipsis-only alternative is given a deeply-negative precedence
        // so that contexts admitting both `block` and `case_block` (e.g.
        // function bodies, finally-clauses) continue to prefer `block`.
        case_block: $ => choice(
            prec(-1, seq("{", "}")),
            seq("{", repeat1($.case_clause), "}"),
            prec(-10, seq("{", $.semgrep_ellipsis, "}")),
        ),

        // LANG-492: accept ellipsis / ellipsis-metavariable in type-argument
        // position, e.g. `List[$...TS]` or `Map[$K, ...]`. Replace the
        // upstream rule to keep a single shared comma-separated repeat,
        // avoiding parser-table conflicts with `tuple_type` (which also
        // begins with `_type ,`).
        type_arguments: $ =>
            seq(
                "[",
                trailingCommaSep1(choice(
                    $._type,
                    $.semgrep_ellipsis,
                    $.semgrep_ellipsis_metavariable,
                )),
                "]",
            ),

        // LANG-496: `$F _` eta-expansion. Upstream `postfix_expression`
        // restricts the right-hand side to an `_identifier` (identifier or
        // operator_identifier), which excludes `_` (a `wildcard`). Add an
        // alternative that pairs the same operand choice with a literal `_`
        // so that any `<expr> _` form (including `$F _`) parses as a
        // postfix_expression.
        postfix_expression: ($, previous) => choice(
            previous,
            prec.left(
                5, // PREC.postfix
                seq(
                    choice($.infix_expression, $.prefix_expression, $._simple_expression),
                    "_",
                ),
            ),
        ),

        // Semgrep pattern: $DECL $NAME = expr
        // Matches val/var definitions where the keyword is abstracted by a
        // metavariable, e.g. `$DECL $SECRET = "..."`.
        semgrep_val_or_var_definition: $ =>
            seq(
                field("keyword", $.semgrep_metavariable),
                field("pattern", choice($._pattern, $.identifiers)),
                optional(seq(":", field("type", $._type))),
                "=",
                field("value", $._indentable_expression),
            ),

        _definition: ($, previous) => choice(previous, $.semgrep_val_or_var_definition),

        // Upstream grammar fixes (until merged upstream)

        // Fix: limit constructor annotation to single argument list.
        // The base `annotation` rule uses `repeat($.arguments)` which greedily
        // consumes class_parameters as annotation arguments in constructors
        // like `class Foo @Inject()(val x: Int)`.
        _constructor_annotation: $ =>
            prec.right(
                seq(
                    "@",
                    field("name", $._simple_type),
                    field("arguments", optional($.arguments)),
                ),
            ),

        // Fix: allow empty blocks in quote expressions.
        quote_expression: ($, _previous) =>
            prec.left(
                10, // PREC.macro
                seq(
                    "'",
                    choice(seq("{", optional($._block), "}"), seq("[", $._type, "]"), $.identifier),
                ),
            ),

        // Fix: support by-name repeated parameter types (=> T*).
        repeated_parameter_type: ($, _previous) =>
            prec.left(
                5, // PREC.postfix
                seq(field("type", choice($._type, $.lazy_parameter_type)), "*"),
            ),

        _class_constructor: ($, _previous) =>
            seq(
                field("name", $._identifier),
                field("type_parameters", optional($.type_parameters)),
                optional($._constructor_annotation),
                optional($.access_modifier),
                field(
                    "class_parameters",
                    repeat(seq(optional($._automatic_semicolon), $.class_parameters)),
                ),
            ),

        // Feat: Scala 2 symbol literal support.
        // Deprecated in Scala 3 but still accepted. Lower precedence so
        // quote_expression wins in Scala 3 contexts.
        symbol_literal: $ =>
            prec(-1, seq("'", field("name", $.identifier))),
    },
});

// Local helpers (the upstream grammar.js defines these, but they are not
// exported from the module).
function sep1(delimiter, rule) {
    return seq(rule, repeat(seq(delimiter, rule)));
}

function trailingCommaSep1(rule) {
    return seq(sep1(",", rule), optional(","));
}
