/*
  semgrep-solidity

  Extends the standard solidity grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-solidity/grammar');

module.exports = grammar(base_grammar, {
  name: 'solidity',

  conflicts: ($, previous) => previous.concat([
    [$.source_file, $._declaration]
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {

      // Entry point. No need for the __SEMGREP_EXPRESSION hack here because
      // Solidity restricts what can appear at the toplevel, so no
      // ambiguity for the semgrep extensions.
        source_file: ($, previous) => {
          return choice(
            previous,
            repeat1($.statement),
            $.expression,
            $.constructor_definition,
            $.modifier_definition,
            $.event_definition,
          );
        },

        // Metavariables. No need to patch the identifier rule because
        // Solidity already accepts '$' as part of an identifier

        // Metavariables for Solidity versions
        _pragma_version_constraint: ($, previous) => {
            return choice(
                previous,
                seq(
                    optional(
                        $.solidity_version_comparison_operator
                    ),
                    $.identifier
                ),
            )
        },
      
      // Ellipsis
        expression: ($, previous) => {
            return choice(
                previous,
                $.ellipsis,
                $.deep_ellipsis,
                $.member_ellipsis_expression
            );
        },

        // Statement ellipsis: src: semgrep-csharp trick
       expression_statement: ($, previous) => {
          return choice(
                previous,
                prec.right(100, seq($.ellipsis, ';')),  // expression ellipsis
                prec.right(100, $.ellipsis),  // statement ellipsis
          );
        },

       // TODO: how to use PREC.MEMBER from original grammar instead of hardcoded value?
       member_ellipsis_expression : $ => prec(1, seq(
            field('object', choice(
                $.expression,
                $.identifier,
            )),
            '.',
            $.ellipsis
       )),

        _contract_member: ($, previous) => {
            return choice(
               previous,
               $.ellipsis
            );
        },
        struct_member: ($, previous) => {
            return choice(
               previous,
               $.ellipsis
            );
        },

        parameter: ($, previous) => {
            return choice(
               previous,
               $.ellipsis
            );
        },

        event_parameter: ($, previous) => {
            return choice(
               previous,
               $.ellipsis
            );
        },

        for_statement: ($, previous) => {
            return choice(
               previous,
               seq('for', '(', $.ellipsis, ')', $.statement)
            );
        },

        inheritance_specifier: ($, previous) => {
            return choice(
                previous,
                $.ellipsis
            );
        },

        // AKA enum_member
        enum_body: ($, previous) => {
            return choice(
                previous,
                seq('{', $.ellipsis, '}')
            );
        },

        // The actual ellipsis rules
        deep_ellipsis: $ => seq(
            '<...', $.expression, '...>'
        ),

        ellipsis: $ => '...',
  }
});

// copy-pasted from the original grammar, because of our copy-paste of enum_declaration
// once the original grammar is rewritten with a enum_member, we would not need
// those defs anymore
function commaSep1(rule) {
    return seq(
        rule,
        repeat(
            seq(
                ',',
                rule
            )
        ),
        optional(','),
    );
}

function commaSep(rule) {
    return optional(commaSep1(rule));
}
