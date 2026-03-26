module.exports = {
    conflicts: ($, previous) => previous,
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
    },
};
