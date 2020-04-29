open Ast_grammar_normalized2

let pr s = print_string s

let symbol x = 
  pr x

let atom = function
 | SYMBOL x -> symbol x
 | TOKEN -> pr "TOKEN"
 | STRING s -> pr "\""; pr s; pr "\""

let rec simple = function
 | ATOM x -> atom x
 | SEQ(xs) -> xs |> List.iter (fun x -> 
          simple x;
          pr " ";
    )
  | REPEAT x -> pr "repeat("; simple x; pr ")"
  | REPEAT1 x -> pr "repeat1("; simple x; pr ")"
  | OPTION x -> pr "option("; simple x; pr ")"

let rule_body = function
  | SIMPLE x -> 
      simple x; pr " { } "
  | CHOICE xs ->
    pr "\n";
    xs |> List.iter (fun x ->
      pr " | ";
      simple x; pr " { } ";
      pr "\n";
    )

let generate_menhir_grammar (_start, rules) =
 rules |> List.iter (fun (id, body) -> 
   symbol id;
   pr ": ";
   rule_body body;
   pr "\n";
   pr "\n";
 )
