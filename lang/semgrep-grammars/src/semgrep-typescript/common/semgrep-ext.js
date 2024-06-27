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
  ]),

  rules: {
    program: ($, previous) => choice(
      previous,
      // Used as a semgrep pattern
      $.switch_case,
    ),

    /*
      semgrep metavariables are already valid javascript/typescript
      identifiers so we do nothing for them.
    */

    semgrep_ellipsis: $ => '...',
    semgrep_metavar_ellipsis: $ => /\$\.\.\.[A-Z_][A-Z_0-9]*/,

    /* In the expression context, there are LR(1) conflicts with spread and
     * rest. I (nmote) don't think that these are true ambiguities, but just in
     * case we'll declare conflicts and set this to low dynamic precedence so as
     * to avoid incorrectly parsing target programs. */
    semgrep_expression_ellipsis: $ => prec.dynamic(-1337, '...'),

    primary_expression: ($, previous) => choice(
      previous,
      $.semgrep_expression_ellipsis,
    ),

    _jsx_attribute: ($, previous) => choice(
      previous,
      $.semgrep_ellipsis,
      $.semgrep_metavar_ellipsis
    ),

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
