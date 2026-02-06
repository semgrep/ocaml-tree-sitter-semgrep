/*
 * Semgrep extensions for PHP grammar.
 * These extensions are shared between both php and php_only variants.
 *
 * Precedence values from base PHP grammar:
 * PREC.NEW = 24, PREC.CALL = 25, PREC.MEMBER = 26
 */

const semgrep_metavariable_regex = String.raw`\$[A-Z][A-Za-z0-9_]*`;

module.exports = {
    conflicts: ($, previous) => previous.concat([
        // Ellipsis can conflict with PHP's variadic placeholder
        [$.semgrep_ellipsis, $.variadic_placeholder],
        [$.semgrep_ellipsis, $.variadic_unpacking],
        // Primary expression and statement can both contain ellipsis
        [$.primary_expression, $.statement],
        // Ellipsis in arrays
        [$.primary_expression, $.array_element_initializer],
        // Ellipsis in arguments
        [$.primary_expression, $.argument],
        // Metavariable as name or callable
        [$._list_destructing],
        [$._list_destructing, $._array_destructing_element],
        // Arguments rule conflicts
        [$.arguments],
        [$.arguments, $.argument],
        [$.primary_expression, $.arguments, $.argument],
        // Match block conflicts
        [$.match_block],
        [$.match_block, $.primary_expression],
        // Array destructuring conflicts
        [$.primary_expression, $._array_destructing_element, $.array_element_initializer],

        [$.primary_expression, $.variable_name, $.name],
        [$.variable_name, $.name],
    ]),

    rules: {
        semgrep_metavariable: _ => new RegExp(semgrep_metavariable_regex),

        semgrep_ellipsis: _ => '...',

        // Named ellipsis: $...ARGS
        semgrep_ellipsis_metavariable: _ => /\$\.\.\._?[A-Z][A-Z_0-9]*/,

        // Deep expression: <... expr ...>
        deep_expression: $ => prec(10, seq(
            '<...',
            $.expression,
            '...>',
        )),

        semgrep_ellipsis_method_chain: $ => prec(27, seq( // PREC.MEMBER + 1
            field('object', $._dereferencable_expression),
            '->',
            '...',
        )),


        variable_name: ($, previous) => choice(
            $.semgrep_metavariable,
            previous,
        ),

        // NOTE: we copy the definition here (to combine with semgrep_metavariable)
        // since name cannot be defined as a choice with the previous definition
        // and also be used as the token for `word`.
        name: ($, previous) => choice(
            $.semgrep_metavariable,
            previous,
        ),

        primary_expression: ($, previous) => choice(
            previous,
            $.semgrep_metavariable,
            $.semgrep_ellipsis,
            $.deep_expression,
        ),

        // Extend arguments to support ellipsis at top level
        arguments: ($, previous) => choice(
            previous,
            seq(
                '(',
                optional(seq(
                    choice($.argument, $.semgrep_ellipsis, $.semgrep_ellipsis_metavariable),
                    repeat(seq(',', choice($.argument, $.semgrep_ellipsis, $.semgrep_ellipsis_metavariable))),
                    optional(',')
                )),
                ')'
            )
        ),

        // Extend argument to support ellipsis
        argument: ($, previous) => choice(
            $.semgrep_ellipsis,
            $.semgrep_ellipsis_metavariable,
            previous,
        ),

        // Extend statement to allow standalone ellipsis
        statement: ($, previous) => choice(
            $.semgrep_ellipsis,
            previous,
        ),

        // Extend array elements to support ellipsis
        array_element_initializer: ($, previous) => choice(
            $.semgrep_ellipsis,
            $.semgrep_ellipsis_metavariable,
            previous,
        ),

        // Extend class/trait/interface members to support ellipsis
        _member_declaration: ($, previous) => choice(
            $.semgrep_ellipsis,
            previous,
        ),

        // Extend simple_parameter to support ellipsis
        simple_parameter: ($, previous) => choice(
            $.semgrep_ellipsis,
            $.semgrep_ellipsis_metavariable,
            previous,
        ),

        // Method Chain Ellipsis
        member_call_expression: ($, previous) => choice(
            previous,
            prec(25, seq( // PREC.CALL
                field('object', $.semgrep_ellipsis_method_chain),
                '->',
                field('name', $._member_name),
                field('arguments', $.arguments),
            )),
        ),

        // Extend member_access_expression to support $obj->...->property
        member_access_expression: ($, previous) => choice(
            previous,
            prec(26, seq( // PREC.MEMBER
                field('object', $.semgrep_ellipsis_method_chain),
                '->',
                field('name', $._member_name),
            )),
        ),

        // Extend match_block to support ellipsis
        match_block: ($, previous) => choice(
            previous,
            prec.left(seq(
                '{',
                optional(seq(
                    choice($.match_conditional_expression, $.match_default_expression, $.semgrep_ellipsis),
                    repeat(seq(',', choice($.match_conditional_expression, $.match_default_expression, $.semgrep_ellipsis))),
                    optional(',')
                )),
                '}'
            ))
        ),

        // Extend _array_destructing_element to support ellipsis
        _array_destructing_element: ($, previous) => choice(
            $.semgrep_ellipsis,
            $.semgrep_ellipsis_metavariable,
            previous,
        ),

        // Extend _list_destructing to support ellipsis
        _list_destructing: ($, previous) => choice(
            previous,
            seq(
                alias(/list/i, 'list'),
                '(',
                optional(seq(
                    optional(choice($._array_destructing_element, $.semgrep_ellipsis)),
                    repeat(seq(',', optional(choice($._array_destructing_element, $.semgrep_ellipsis)))),
                    optional(',')
                )),
                ')'
            )
        ),
    }
};
