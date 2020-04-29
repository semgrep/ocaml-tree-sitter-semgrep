
type ident = string
  [@@deriving show]

type atom =
  | SYMBOL of ident 
  | TOKEN 
  | STRING of string 
  [@@deriving show { with_path = false }]

type simple =
  | ATOM of atom 
  | SEQ of simple list 
  | REPEAT of simple | REPEAT1 of simple
  | OPTION of simple 
  [@@deriving show { with_path = false }]

type rule_body =
  | CHOICE of simple list 
  | SIMPLE of simple 
  [@@deriving show { with_path = false }]

type rule = (ident * rule_body)
  [@@deriving show]
type rules = rule list
  [@@deriving show]

type grammar = (ident * rules)
  [@@deriving show]

type t = grammar
  [@@deriving show]

(* basic visitor *)
let rec visit_rules fatom xs =
  xs |> List.iter (fun (_id, body) ->  visit_rule_body fatom body)
and visit_rule_body fatom = function
  | CHOICE xs -> List.iter (visit_simple fatom) xs
  | SIMPLE x -> visit_simple fatom x
and visit_simple fatom = function
  | ATOM x -> fatom x
  | SEQ xs -> List.iter (visit_simple fatom) xs
  | REPEAT x | REPEAT1 x | OPTION x -> visit_simple fatom x