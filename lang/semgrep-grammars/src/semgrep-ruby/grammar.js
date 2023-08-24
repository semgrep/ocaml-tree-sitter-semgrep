/*
  semgrep-ruby

  Extends the standard ruby grammar with semgrep pattern constructs.
*/

/*

(2023-02-25) A warning from Emma: I spent about a week trying to make
pattern parsing work before I gave up. I spent so much time because the
existing dyp parser has a long startup cost to create the parser (see `pp`
in the library). However, I ran into too many problems. Some of these may
be my own misunderstanding, some of these are inherent to the existing
grammar:

1. It is hard to distinguish a range (`a...b`) from ellipsis. In particular,
the example I worked with was:

```
$V = get_data user
...
eval $V
```

With my naive modification of the grammar, this parses as `user ...` being
a range with null at the other end. It's not clear to me why that's possible,
which makes it hard to figure out how to avoid it.

2. This parser without modifications appears to interpret regex strings
oddly. The `regexp_string.sgrep` in the ruby pattern tests ends up being
parsed into a ConcatString.

3. There was some strange behavior with underscores. If you look at my
modification of `call`, I use `$._primary` where the original used
`$.primary`. When I didn't, I got an error `Undefined symbol 'primary'`.
I don't know why I got that error or the _ fixed it. I also had to modify
`call` by making a rule for `_call`. I did that because otherwise my change
had no effect. An interesting note is that a rule for `call_` exists in the
grammar.

This is particularly interesting to me because I tried a similar modification
for `command_call_with_block`, which doesn't have a corresponding rule for
`command_call_with_block_`. When I made a rule for `command_call_with_block`,
the generated grammar didn't modify the original `command_call_with_block` but
made a new rule `command_call_with_block_`. When I made a rule for
`_command_call_with_block`, I failed one of the test cases because it parsed
something that should have been a `call` as a `chained_command_call`.

Other grammars seem to make changes as I would have expected, so I'm particularly
baffled.

I started this as a side project, so I don't have the time to investigate
these in depth. I'm recording them for whoever tries this after me. They
may or may not still be present issues.

*/

const standard_grammar = require('tree-sitter-ruby/grammar');

module.exports = grammar(standard_grammar, {
  name: 'ruby',
  // word: $ => $.old_identifier,

  externals: ($, previous) => previous.concat([
    // See the "sgrep-ext" in scanner.cc for more on how this
    // works. Just assume that this token is correctly put in
    // for all instances of a real Semgrep ellipsis, followed
    // by a newline.
    $.semgrep_ellipsis_followed_by_newline
  ]),

  /* There are a few cases for Semgrep ellipses that we would like to
     be able to parse.

     I identify the following situations as pertinent to us:
     1) singular statements of Semgrep ellipses, e.g.
          foo()
          ...
          bar()
     2) ellipses in function arguments or function parameters, e.g.
          foo(..., 1)
          or
          def method (x, ...)
          end
     3) ellipses in dot access chains
     4) (less important) ellipses for standalone expressions

     The former is hard because of conflating it with range expressions,
     which look like e1 ... e2. See scanner.cc and our accompanying sgrep-ext
     for how the $.semgrep_ellipsis_followed_by_newline solves this.

     For the second, Ruby has a notion of "forward parameters", which happen
     to look identical to this use case. So we can piggy-back off of that.

     For the third, expressions in Ruby can be of the form <e>.<id>, meaning
     that we can just permit identifiers to be ellipses, and this will be fine.
     This actually solves the fourth as well.
   */

  rules: {
    /* Extend identifier to accept metavariable names
       The precedence on the token is -1 because global variables
       in Ruby also start with $. To satisfy tests, global_variable
       needs to have higher precedence than identifier */
    identifier: ($, previous) => token(prec(-1,
      choice(
        previous,
        /\$[A-Z_][A-Z_0-9]*/,
        // Need a high precedence here, so that "$...X" is not parsed
        // as a range expression from $ to X.
        token(prec(1000, /\$\.\.\.[A-Z_][A-Z_0-9]*/)),
        // Same here, so it works within dot accesses.
        alias(token(prec(1000, "...")), $.semgrep_ellipsis)
     ))
    ),

    deep_ellipsis: $ => seq('<...', $._expression, '...>'),

    _expression: ($, previous) => {
      return choice(
        previous,
        $.semgrep_ellipsis_followed_by_newline,
        $.deep_ellipsis
      );
    },

    _statement: ($, previous) =>
      // Theoretically, it should be possible to reach a "..." from a
      // statement, because a statement includes expresisons which include
      // identifiers.
      // But this makes some more things parse -- in particular, the
      // "Ellipsis in interpolation" test. So sure, why not.
      choice(
        previous,
        alias("...", $.semgrep_ellipsis),
        // High prec so that we prefer this over expressions.
        // In theory this probably doesn't add anything, but it doesn't
        // hurt to play it safe.
        prec(1000, $.semgrep_ellipsis_followed_by_newline)
      )
    ,

    /* ellipsis: $ =>  '...',

    deep_ellipsis: $ => seq('<...', $._expression, '...>'),

    _expression: ($, previous) => {
      return choice(
        previous,
        $.ellipsis,
        $.deep_ellipsis,
      );
    },

    _call: ($, previous) => prec.left(
      56,
      seq(
        field(
          "receiver",
          $._primary
        ),
        choice(
          ".",
          "&."
        ),
        field(
          "method",
          choice(
            $.identifier,
            $.operator,
            $.constant,
            $.argument_list,
            $.ellipsis
          )
        )
      )
    ), */

  }
});
