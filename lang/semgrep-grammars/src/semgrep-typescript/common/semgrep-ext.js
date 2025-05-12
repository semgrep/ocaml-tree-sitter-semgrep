/*
 * A partial tree-sitter grammar object containing the semgrep extensions to the
 * typescript grammar. This way, these extensions can be reused in both the TSX
 * and the TS grammars.
 *
 * Even if we only use one of these parsers to parse patterns, it's simpler to
 * keep the CSTs the same and there's little downside in doing so.
 */
module.exports = {
  conflicts: ($, previous) => previous.concat([
    [$.semgrep_expression_ellipsis, $.spread_element],
    [$.semgrep_expression_ellipsis, $.rest_pattern],
    [$.semgrep_expression_ellipsis, $.rest_type],
    [$.semgrep_expression_ellipsis, $.rest_type, $.spread_element, $.rest_pattern],
    [$.semgrep_expression_ellipsis, $.spread_element, $.rest_pattern],
    [$.semgrep_expression_ellipsis, $.semgrep_ellipsis],
    [$.class_body, $.public_field_definition],
    [$.pair, $.pair_pattern],
  ]),

  rules: {
    program: ($, previous) => choice(
      previous,
      // Used as a semgrep pattern
      $.switch_case,
      $.semgrep_expression,
    ),

    // Alternate "entry point". Allows parsing a standalone expression.
    semgrep_expression: $ => seq('__SEMGREP_EXPRESSION', $.semgrep_pattern),

    semgrep_pattern: $ => choice(
      $.expression,
      $.pair,
    ),

    semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,

    _jsx_child: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_metavariable,
    ),

    // To permit {...}, for `...` in objects.
    pair: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    // To permit `(...) => 1`, for `...` in parameter patterns.
    pair_pattern: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
    ),

    /*
      semgrep metavariables are already valid javascript/typescript
      identifiers so we do nothing for them.
    */

    semgrep_ellipsis: $ => '...',

    /* ellipsis in function parameters
     * e.g. function foo(..., x, ...)
     */
    _formal_parameter: $ => choice(
      $.semgrep_ellipsis,
      $.required_parameter,
      $.optional_parameter,
    ),

    /* This part is copied from the original grammar to add `$.semgrep_ellipsis`
     * as one of the choices. Make sure it is in sync with the original grammar
     * and update it if necessary.
     * TODO: update the original grammar to include an intermediate `class_element`
     * rule so that we can avoid copying and pasting the original rule here.
     */
    class_body: $ => seq(
      '{',
      repeat(choice(
        $.semgrep_ellipsis,
        $.decorator,
        seq($.method_definition, optional($._semicolon)),
        // As it happens for functions, the semicolon insertion should not
        // happen if a block follows the closing paren, because then it's a
        // *definition*, not a declaration. Example:
        //     public foo()
        //     { <--- this brace made the method signature become a definition
        //     }
        // The same rule applies for functions and that's why we use
        // "_function_signature_automatic_semicolon".
        seq($.method_signature, choice($._function_signature_automatic_semicolon, ',')),
        seq(
          choice(
            $.abstract_method_signature,
            $.index_signature,
            $.method_signature,
            $.public_field_definition
          ),
          choice($._semicolon, ',')
        )
      )),
      '}'
    ),

/* TODO: restore this when the changes are made in semgrep.
   Remove the XXXXXXX when uncommenting.

   You also need to restore the test file:
     lang/semgrep-grammars/src/semgrep-typescript/tsx/corpus/semgrep-ext.txt
   See the original PR:
     https://github.com/semgrep/ocaml-tree-sitter-semgrep/pull/488

    semgrep_metavar_ellipsis: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*XXXXXXX/,
/*
    /* In the expression context, there are LR(1) conflicts with spread and
     * rest. I (nmote) don't think that these are true ambiguities, but just in
     * case we'll declare conflicts and set this to low dynamic precedence so as
     * to avoid incorrectly parsing target programs. */
    semgrep_expression_ellipsis: $ => prec.dynamic(-1337, '...'),

    primary_expression: ($, previous) => choice(
      previous,
      $.semgrep_expression_ellipsis,
    ),

/* TODO: restore this when the changes are made in semgrep.
    _jsx_attribute: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_metavar_ellipsis
    ),
*/
    // TODO Remove this when we update tree-sitter-typescript past
    // https://github.com/tree-sitter/tree-sitter-typescript/pull/239. I (nmote)
    // ran into unrelated issues updating it, documented in
    // https://linear.app/r2c/issue/PA-2572/address-error-when-updating-tree-sitter-typescript.
    comment: ($, previous) => token(choice(
      previous,
      // https://tc39.es/ecma262/#sec-html-like-comments
      seq('<!--', /.*/),
      // This allows code to exist before this token on the same line.
      //
      // Technically, --> is supposed to have nothing before it on the same line
      // except for comments and whitespace, but that is difficult to express,
      // and in general tree sitter grammars tend to prefer to be overly
      // permissive anyway.
      //
      // This approach does not appear to cause problems in practice.
      seq('-->', /.*/)
   )),
  }
}
