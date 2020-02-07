(* Auto-generated from "grammar.atd" *)
[@@@ocaml.warning "-27-32-35-39"]

type token_rule = Grammar_t.token_rule = {
  rule_type: string;
  name: string;
  value: string
}

type symbol_rule = Grammar_t.symbol_rule = {
  rule_type: string;
  name: string;
  value: string
}

type pattern_rule = Grammar_t.pattern_rule = {
  rule_type: string;
  name: string;
  value: string
}

type _rules = Grammar_t._rules = {
  variable: pattern_rule option;
  number: pattern_rule option;
  comment: pattern_rule option
}

type rules = Grammar_t.rules

type rule = Grammar_t.rule

type grammar = Grammar_t.grammar = {
  name: string;
  rules: rules;
  extras: rules;
  externals: rules;
  sypertypes: rules;
  inline: string list option;
  conflicts: string list list option;
  word: string option
}

val write_token_rule :
  Bi_outbuf.t -> token_rule -> unit
  (** Output a JSON value of type {!token_rule}. *)

val string_of_token_rule :
  ?len:int -> token_rule -> string
  (** Serialize a value of type {!token_rule}
      into a JSON string.
      @param len specifies the initial length
                 of the buffer used internally.
                 Default: 1024. *)

val read_token_rule :
  Yojson.Safe.lexer_state -> Lexing.lexbuf -> token_rule
  (** Input JSON data of type {!token_rule}. *)

val token_rule_of_string :
  string -> token_rule
  (** Deserialize JSON data of type {!token_rule}. *)

val write_symbol_rule :
  Bi_outbuf.t -> symbol_rule -> unit
  (** Output a JSON value of type {!symbol_rule}. *)

val string_of_symbol_rule :
  ?len:int -> symbol_rule -> string
  (** Serialize a value of type {!symbol_rule}
      into a JSON string.
      @param len specifies the initial length
                 of the buffer used internally.
                 Default: 1024. *)

val read_symbol_rule :
  Yojson.Safe.lexer_state -> Lexing.lexbuf -> symbol_rule
  (** Input JSON data of type {!symbol_rule}. *)

val symbol_rule_of_string :
  string -> symbol_rule
  (** Deserialize JSON data of type {!symbol_rule}. *)

val write_pattern_rule :
  Bi_outbuf.t -> pattern_rule -> unit
  (** Output a JSON value of type {!pattern_rule}. *)

val string_of_pattern_rule :
  ?len:int -> pattern_rule -> string
  (** Serialize a value of type {!pattern_rule}
      into a JSON string.
      @param len specifies the initial length
                 of the buffer used internally.
                 Default: 1024. *)

val read_pattern_rule :
  Yojson.Safe.lexer_state -> Lexing.lexbuf -> pattern_rule
  (** Input JSON data of type {!pattern_rule}. *)

val pattern_rule_of_string :
  string -> pattern_rule
  (** Deserialize JSON data of type {!pattern_rule}. *)

val write_rules :
  Bi_outbuf.t -> rules -> unit
  (** Output a JSON value of type {!rules}. *)

val string_of_rules :
  ?len:int -> rules -> string
  (** Serialize a value of type {!rules}
      into a JSON string.
      @param len specifies the initial length
                 of the buffer used internally.
                 Default: 1024. *)

val read_rules :
  Yojson.Safe.lexer_state -> Lexing.lexbuf -> rules
  (** Input JSON data of type {!rules}. *)

val rules_of_string :
  string -> rules
  (** Deserialize JSON data of type {!rules}. *)

val write_rule :
  Bi_outbuf.t -> rule -> unit
  (** Output a JSON value of type {!rule}. *)

val string_of_rule :
  ?len:int -> rule -> string
  (** Serialize a value of type {!rule}
      into a JSON string.
      @param len specifies the initial length
                 of the buffer used internally.
                 Default: 1024. *)

val read_rule :
  Yojson.Safe.lexer_state -> Lexing.lexbuf -> rule
  (** Input JSON data of type {!rule}. *)

val rule_of_string :
  string -> rule
  (** Deserialize JSON data of type {!rule}. *)

val write_grammar :
  Bi_outbuf.t -> grammar -> unit
  (** Output a JSON value of type {!grammar}. *)

val string_of_grammar :
  ?len:int -> grammar -> string
  (** Serialize a value of type {!grammar}
      into a JSON string.
      @param len specifies the initial length
                 of the buffer used internally.
                 Default: 1024. *)

val read_grammar :
  Yojson.Safe.lexer_state -> Lexing.lexbuf -> grammar
  (** Input JSON data of type {!grammar}. *)

val grammar_of_string :
  string -> grammar
  (** Deserialize JSON data of type {!grammar}. *)

