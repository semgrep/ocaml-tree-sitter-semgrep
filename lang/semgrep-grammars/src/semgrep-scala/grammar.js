/*
  semgrep-scala

  Extends the standard Scala grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-scala/grammar');

const semgrepExt = require('./common/semgrep-ext');

// _alpha_identifier is the `word` rule; it must remain a terminal (regex)
// token. Remove it from the base grammar object before extending so that our
// identifier extension (which wraps it inside a choice) doesn't conflict with
// the word setting.
delete base_grammar.grammar.word;

module.exports = grammar(base_grammar, {
    name: 'scala',
    ...semgrepExt,
});
