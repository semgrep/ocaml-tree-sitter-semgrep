/*
  semgrep-php_only

  Extends the standard php_only grammar with semgrep pattern constructs.
*/

const php_only_grammar = require('tree-sitter-php/php_only/grammar');

const semgrepExt = require('../common/semgrep-ext');

// Delete the `word`, since it is set to `name`, which we need to make name a
// non-terminal production (to allow for it to be a choice between metavariable
// and the prior `name` production). But the rule used for `word` (for keyword
// extraction) cannot be a non-terminal.
delete php_only_grammar.grammar.word;

module.exports = grammar(php_only_grammar, {
  name: 'php_only',
  ...semgrepExt,
});
