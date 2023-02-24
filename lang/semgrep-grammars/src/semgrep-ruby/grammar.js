/*
  semgrep-ruby

  Extends the standard ruby grammar with semgrep pattern constructs.
*/

const standard_grammar = require('tree-sitter-ruby/grammar');

module.exports = grammar(standard_grammar, {
  name: 'ruby',
  word: $ => $.old_identifier,

  rules: {
    old_identifier: $ => token(
      seq(
        /[^\x00-\x1F\sA-Z0-9:;`"'@$#.,|^&<=>+\-*/\\%?!~()\[\]{}]/,
        /[^\x00-\x1F\s:;`"'@$#.,|^&<=>+\-*/\\%?!~()\[\]{}]*/,
        /(\?|\!)?/
      )
    ),

    /* Extend identifier to accept metavariable names
       The precedence on the token is -1 because global variables
       in Ruby also start with $. To satisfy tests, global_variable
       needs to have higher precedence than identifier */
    identifier: ($, previous) => token(prec(-1, 
      seq(
        /[^\x00-\x1F\sA-Z0-9:;`"'@#.,|^&<=>+\-*/\\%?!~()\[\]{}]/,
        /[^\x00-\x1F\s:;`"'@$#.,|^&<=>+\-*/\\%?!~()\[\]{}]*/,
        /(\?|\!)?/
      ))
    ),

  /*  semgrep_dots: $ => '...',

    _expression: ($, previous) => {
      return choice(
        previous,
        $.semgrep_dots,
      );
    }, */

  /*  semgrep_dots: $ => '...',

    _expression: ($, previous) => {
      return choice(
        $.semgrep_dots,
        ...previous.members
      );
    }
*/
  }
});
