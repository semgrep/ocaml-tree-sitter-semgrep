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
        semgrep_metavariable: _ => token(prec(1, /\$[A-Z][A-Za-z0-9_]*/)),
        semgrep_ellipsis: _ => token(prec(1, '...')),
        semgrep_ellipsis_metavariable: _ => token(prec(1, /\$\.\.\.[A-Za-z_][A-Za-z0-9_]*/)),
        deep_expression: $ => prec(10, seq('<...', $.expression, '...>')),

        _top_level_definition: ($, previous) => choice(
            $.semgrep_expression,
            $.semgrep_statement,
            $.semgrep_member_decl,
            previous,
        ),
        _simple_expression: ($, previous) => choice(
            previous,
            $.semgrep_metavariable,
            $.deep_expression,
            $.semgrep_ellipsis_metavariable,
            $.semgrep_ellipsis,
        ),
        _pattern: ($, previous) => choice(previous, $.semgrep_ellipsis),
        parameter: ($, previous) => choice(previous, $.semgrep_ellipsis),
        class_parameter: ($, previous) => choice(previous, $.semgrep_ellipsis),
        enumerator: ($, previous) => choice(previous, prec(1, $.semgrep_ellipsis)),

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
    },
});
