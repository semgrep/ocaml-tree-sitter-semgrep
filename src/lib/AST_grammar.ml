(*
   Conversion and simplification from type specified in Tree_sitter.atd.
*)

type ident = string

type rule_body =
  (* composite (nodes) *)
  | Repeat of rule_body
  | Choice of rule_body list
  | Seq of rule_body list

  (* atomic (leaves) *)
  | Symbol of ident
  | String of string
  | Pattern of string

type rule = (ident * rule_body)

type grammar = {
  name: ident;
  rules: rule list;
}

(* alias *)
type t = grammar

(*
   Simple translation without normalization.
*)
let rec translate (x : Tree_sitter_t.rule_body) =
  match x with
  | SYMBOL ident -> Symbol ident
  | STRING s -> String s
  | PATTERN s -> Pattern s
  | REPEAT x -> Repeat (translate x)
  | CHOICE l -> Choice (List.map translate l)
  | SEQ l -> Seq (List.map translate l)
  | PREC (_prio, x) -> translate x
  | PREC_DYNAMIC (_prio, x) -> translate x
  | PREC_LEFT (_opt_prio, x) -> translate x
  | PREC_RIGHT (_opt_prio, x) -> translate x

(*
   Algorithm: convert the nodes of tree from unnormalized to normalized,
   starting from the leaves.
*)
let rec normalize x =
  match x with
  | Symbol _
  | String _
  | Pattern _
  | Repeat _ as x -> x
  | Choice l -> Choice (List.map normalize l |> flatten_choice)
  | Seq l -> Seq (List.map normalize l |> flatten_seq)

and flatten_choice normalized_list =
  normalized_list
  |> List.map (function
    | Choice l -> l
    | other -> [other]
  )
  |> List.flatten

and flatten_seq normalized_list =
  normalized_list
  |> List.map (function
    | Seq l -> l
    | other -> [other]
  )
  |> List.flatten

let translate_rules rules =
  List.map (fun (name, body) -> (name, translate body |> normalize)) rules

let of_tree_sitter (x : Tree_sitter_t.grammar) : t =
  let rules = translate_rules x.rules in
  {
    name = x.name;
    rules = rules;
  }
