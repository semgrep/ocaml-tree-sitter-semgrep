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

  rules: {
    // old_identifier: $ => token(
    //  seq(
    //    /[^\x00-\x1F\sA-Z0-9:;`"'@$#.,|^&<=>+\-*/\\%?!~()\[\]{}]/,
    //    /[^\x00-\x1F\s:;`"'@$#.,|^&<=>+\-*/\\%?!~()\[\]{}]*/,
    //    /(\?|\!)?/
    //  )
    // ),

    /* Extend identifier to accept metavariable names
       The precedence on the token is -1 because global variables
       in Ruby also start with $. To satisfy tests, global_variable
       needs to have higher precedence than identifier */
    // identifier: ($, previous) => token(prec(-1, 
    //  seq(
    //    /[^\x00-\x1F\sA-Z0-9:;`"'@#.,|^&<=>+\-*/\\%?!~()\[\]{}]/,
    //    /[^\x00-\x1F\s:;`"'@$#.,|^&<=>+\-*/\\%?!~()\[\]{}]*/,
    //    /(\?|\!)?/
    //  ))
    // ),

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
