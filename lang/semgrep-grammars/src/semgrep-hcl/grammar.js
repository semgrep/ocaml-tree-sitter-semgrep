/*
  semgrep-hcl

  Extends the standard hcl grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-hcl/grammar');

module.exports = grammar(base_grammar, {
  name: 'hcl',

  conflicts: ($, previous) => previous.concat([
     // when added ellipsis for object_elems
     // Unresolved conflict for symbol sequence:
     // object_start  semgrep_ellipsis  •  '['  …
     // Possible interpretations:
     //  1:  object_start  (_expr_term  semgrep_ellipsis)  •  '['  …
     //  2:  object_start  (object_elem  semgrep_ellipsis)  •  '['  …
     [$._expr_term, $.object_elem],
     // The new postfix `_expr_term get_attr ( ... )` (for chained
     // callees like `$NS.$F($ARG)`) shares its prefix with the
     // existing postfix `_expr_term get_attr` production. The `(` (or
     // its absence) disambiguates, but tree-sitter needs this
     // conflict declaration to keep both parses live.
     [$._expr_term],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Entry point
    config_file: ($, previous) => {
      return choice(
        previous,
        $.semgrep_expression
      );
    },

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $.expression),


    // Metavariables
    identifier: ($, previous) => {
      return choice(
        previous,
        $._semgrep_metavariable
      );
    },

    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

    // Ellipsis-metavariable, e.g. `$...ARGS`. Lexed atomically so it wins
    // over the `identifier` + `...` decomposition.
    _semgrep_ellipsis_metavar: $ => token(/\$\.\.\.[A-Z_][A-Z_0-9]*/),


    // Ellipsis
    body: ($, previous) => repeat1(
      choice(
        $.attribute,
        $.block,
        $.semgrep_ellipsis,
        $._semgrep_ellipsis_metavar,
      ),
     ),

    object_elem: ($, previous) => {
      return choice(
        previous,
        $.semgrep_ellipsis,
        $._semgrep_ellipsis_metavar
      );
    },

    // Adds support for:
    //   - semgrep ellipsis (`...`) and `<... e ...>` deep ellipsis;
    //   - the ellipsis-metavariable token `$...X`;
    //   - a postfix function-call production on `_expr_term` so that
    //     calls with a `get_attr`-chain callee like `$NS.$F($ARG)`
    //     or `provider.fn(arg)` parse correctly. The base grammar's
    //     `function_call` (bare-identifier callee) still handles
    //     `foo(x)` unchanged; this new branch reuses the existing
    //     postfix `_expr_term get_attr` production for the callee
    //     prefix, so `foo.bar` (no call) keeps its current parse.
    _expr_term: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.deep_ellipsis,
      $._semgrep_ellipsis_metavar,
      seq(
        $._expr_term,
        $.get_attr,
        $._function_call_start,
        optional($.function_arguments),
        $._function_call_end,
      ),
    ),

    semgrep_ellipsis: $ => '...',

    deep_ellipsis: $ => seq(
      '<...', $.expression, '...>'
    ),

  }
});
