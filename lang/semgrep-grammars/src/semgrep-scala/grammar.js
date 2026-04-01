/*
  semgrep-scala

  Extends the standard Scala grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-scala/grammar');

// _alpha_identifier is the `word` rule; it must remain a terminal (regex)
// token. Remove it from the base grammar object before extending so that our
// identifier extension (which wraps it inside a choice) doesn't conflict with
// the word setting.
delete base_grammar.grammar.word;

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

        // Fix for ResultExpr/BlockResult typed implicit parameter form:
        //   { implicit request: Request[AnyContent] => body }
        // Both the Scala 2.13 and 3.4 specs (§6.23) define ResultExpr as:
        //   (Bindings | (['implicit'] id | '_') ':' CompoundType) '=>' Block
        // The upstream grammar uses seq(optional("implicit"), $._identifier),
        // which cannot accommodate a type annotation. Fixed upstream in our
        // patch (0001-fix-lambda-typed-implicit-parameter.patch); mirrored
        // here in the interim. Split into an explicit 'implicit' branch (with
        // optional type) and a plain identifier branch to avoid new LR
        // conflicts.
        lambda_expression: $ =>
            prec.right(
                seq(
                    optional(seq(field("type_parameters", $.type_parameters), "=>")),
                    field(
                        "parameters",
                        choice(
                            $.bindings,
                            seq("implicit", $._identifier, optional(seq(":", field("type", $._param_type)))),
                            $._identifier,
                            $.wildcard,
                        ),
                    ),
                    choice("=>", "?=>"),
                    $._indentable_expression,
                ),
            ),
    },
});
