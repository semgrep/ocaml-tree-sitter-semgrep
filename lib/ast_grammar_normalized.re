/* Normalized grammar.json, easier to work on */

[@deriving show]
type ident = string;

/* this is easier to translate into OCaml ADTs type definitions */


[@deriving show { with_path : false} ]
type atom =
 | SYMBOL(ident) /* codegen: ident */
 | TOKEN(option(ident))
 ;

[@deriving show { with_path : false} ]
type simple =
 | ATOM(atom)
 | SEQ(list(atom)) /* codegen: (A,B,C,...) */
;

[@deriving show { with_path : false} ]
type rule_body =
 | REPEAT(simple)       /* codegen: list(x) */
 | CHOICE(list(simple)) /* codegen: A(...) | B(...) */
 | OPTION(simple)       /* codegen: option(...) */
 | SIMPLE(simple)
;
[@deriving show]
type rule = (ident, rule_body);

[@deriving show]
type rules = list(rule);

[@deriving show]
type grammar = (ident /* entry point, first rule */, rules);

[@deriving show]
/* alias */
type t = grammar;

let get_rule_body_str = (rule_body: rule_body): string => {
  switch(rule_body) {
  | SIMPLE(ATOM(TOKEN)) => "LEAF"
  | _ => "NON-LEAF"
  }
}