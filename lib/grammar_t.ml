(* Auto-generated from "grammar.atd" *)
              [@@@ocaml.warning "-27-32-35-39"]

type token_rule = { rule_type: string; name: string; value: string }

type symbol_rule = { rule_type: string; name: string; value: string }

type pattern_rule = { rule_type: string; name: string; value: string }

type _rules = {
  variable: pattern_rule option;
  number: pattern_rule option;
  comment: pattern_rule option
}

type rules = _rules option

type rule = [
    `Pattern of pattern_rule
  | `Symbol of symbol_rule
  | `Token of token_rule
]

type grammar = {
  name: string;
  rules: rules;
  extras: rules;
  externals: rules;
  sypertypes: rules;
  inline: string list option;
  conflicts: string list list option;
  word: string option
}
