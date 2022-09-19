/*
  semgrep-cpp

  Extends the standard cpp grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-cpp/grammar');

module.exports = grammar(base_grammar, {
  name: 'cpp',

  conflicts: ($, previous) => previous.concat([
      // C++ allows 'sizeof ...(id)' hence the conflict
      [$.sizeof_expression, $.semgrep_ellipsis],
      // C allows ... in parameters
      [$.parameter_list, $.semgrep_ellipsis],
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // Metavariables

    /* we can't use the usual:

	 identifier: ($, prev) => { return choice(prev, $._semgrep_metavariable);},
         _semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]* /,

      because in tree-sitter-c 'identifier' is used in the 'word:' directive and
      'identifier' then can't be a non-terminal. In other languages this is solved
      by having 'identifier' and a separate '_identifier_token' (e.g., in C#)
    */
    identifier: $ => /\$?[a-zA-Z_]\w*/, // original = /[a-zA-Z_]\w*/

    // Ellipsis

    _expression: ($, previous) => {
      return choice(
        previous,
        $.semgrep_ellipsis,
        $.deep_ellipsis,
      );
    },
	
    semgrep_ellipsis: $ => '...',
    deep_ellipsis: $ => seq('<...', $._expression, '...>'),
  }
});
