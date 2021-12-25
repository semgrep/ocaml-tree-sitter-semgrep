/*
  semgrep-dockerfile

  Extends the standard dockerfile grammar with semgrep pattern constructs.
*/

const base_grammar = require('tree-sitter-dockerfile/grammar');

module.exports = grammar(base_grammar, {
  name: 'dockerfile',

  conflicts: ($, previous) => previous.concat([
  ]),

  rules: {
    _instruction: ($, previous) => choice(
      $.semgrep_ellipsis,
      $.semgrep_metavariable,
      previous
    ),

    // overrides the original definition
    string_array: ($) =>
      seq(
        "[",
        optional(
          seq($._array_element, repeat(seq(",", $._array_element)))
        ),
        "]"
      ),

    _array_element: ($) => choice(
      $.double_quoted_string,
      $.semgrep_ellipsis,
      $.semgrep_metavariable
    ),

    // TODO: support metavariables and ellipses in a bunch of places
    semgrep_metavariable: $ => /\$[A-Z_][A-Z_0-9]*/,
    semgrep_ellipsis: $ => '...',

    /*
      TODO: more syntax ellipsis (e) or metavariables (mv):

      e, mv:
      LABEL multi.label1="value1" multi.label2="value2" other="value3"

      mv:
      MAINTAINER bob

      e, mv:
      EXPOSE 80/tcp 80/udp

      e, mv:
      ENV MY_NAME="John Doe" MY_CAT=fluffy

      e, mv:
      ADD a b /somedir/
      COPY a b /somedir/

      e, mv:
      ADD --chown=55:mygroup a b /somedir/
      COPY --chown=55:mygroup a b /somedir/

      e, mv:
      VOLUME /var/log /var/db

      mv:
      USER patrick
      USER patrick:star

      mv:
      WORKDIR /a

      mv:
      ARG pat
      ARG buildno=42

      mv:
      STOPSIGNAL SIGUSR1

      mv:
      HEALTHCHECK --interval=5m --timeout=3s CMD echo
    */
  }
});
