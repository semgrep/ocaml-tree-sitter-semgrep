/*
  semgrep-php

  Extends the standard php grammar with semgrep pattern constructs.
*/

const php_grammar = require('tree-sitter-php/php/grammar');

const semgrepExt = require('../common/semgrep-ext');

// Delete the `word`, since it is set to `name`, which we need to make name a
// non-terminal production (to allow for it to be a choice between metavariable
// and the prior `name` production). But the rule used for `word` (for keyword
// extraction) cannot be a non-terminal.
delete php_grammar.grammar.word;

module.exports = grammar(php_grammar, {
    name: 'php',
    ...semgrepExt,
});
