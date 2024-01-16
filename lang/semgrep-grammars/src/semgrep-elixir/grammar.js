/*
  semgrep-elixir

  Extends the standard elixir grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-elixir/grammar');

module.exports = grammar(base_grammar, {
  name: 'elixir',

  conflicts: ($, previous) => previous.concat([
  ]),

  /*
     Support for semgrep ellipsis ('...') and metavariables ('$FOO'),
     if they're not already part of the base grammar.
  */
  rules: {
    // No need for _SEMGREP_EXPRESSION hack here, because Elixir allows
    // toplevel expressions.

    // Metavariables
    identifier: ($, previous) => {
      return choice(
        previous,
        $._semgrep_metavariable
      );
    },

    _keyword: ($, previous) => {
	return choice(
	    ...previous.members,
	    $.metavariable_keyword
      );
    },

    metavariable_keyword: $ => seq($._semgrep_metavariable, /:\s/),

    _semgrep_metavariable: $ => token(/\$[A-Z_][A-Z_0-9]*/),

    // Ellipsis
    // No need for extensions to _expressions for ellipsis because
    // Elixir already uses "..." as valid identifiers
    //
    // However, we do need to override the "pair" rule which is used
    // for keyword parameters, arguments, and map items. Otherwise,
    // ellipsis won't work in places where Elixir expects
    // keyword/pairs, such as
    //   foo(some_arg: 0, ...)
    //   %{some_item: 0, ...}
    // Also note that now there is ambiguity whether foo(...) is an
    // identity or pair, we set the pair rule to have a lower
    // precedence
    pair: ($, previous) => {
      return prec(-1, choice(
        previous,
        $.semgrep_ellipsis,
      ));
    },

    semgrep_ellipsis: $ => prec(-1, '...'),

    _expression: ($, previous) => choice(
      ...previous.members,
      $.deep_ellipsis,
    ),

    // The actual ellipsis rules
    deep_ellipsis: $ => seq(
            '<...', $._expression, '...>'
    ),
  }
});
