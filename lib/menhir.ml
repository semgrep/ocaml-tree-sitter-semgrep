open Common
open Ast_grammar_normalized2

type env = {
  tokens: string Common.hashset; (* the TOKEN *)
  start: string;
}

let is_token env s = 
  Hashtbl.mem env.tokens s

let id_to_token id =
  String.uppercase_ascii id

let pr s = print_string s

let symbol env x = 
  let s = 
    if is_token env x
    then id_to_token x
    else x in
  pr s

let atom env = function
 | SYMBOL x -> symbol env x
 | TOKEN -> pr "TOKEN"
 | STRING s -> pr "\""; pr s; pr "\""

let rec simple env = function
 | ATOM x -> atom env x
 | SEQ(xs) -> xs |> List.iter (fun x -> 
          simple env x;
          pr " ";
    )
  | REPEAT x -> pr "list("; simple env x; pr ")"
  | REPEAT1 x -> pr "nonempty_list("; simple env x; pr ")"
  | OPTION x -> pr "option("; simple env x; pr ")"

let rule_body id env = function
  | SIMPLE x -> 
      simple env x; 
      if id = env.start 
      then pr " EOF";
      pr " { } "
  | CHOICE xs ->
    pr "\n";
    xs |> List.iter (fun x ->
      pr " | ";
      simple env x; pr " { } ";
      pr "\n";
    )

let generate_menhir_grammar (start, rules) =
  pr "%{\n";
  pr "%}\n";
  pr "\n";

  let tokens = rules |> Common.map_filter (fun (id, body) ->
        match body with
        | SIMPLE (ATOM (TOKEN)) -> Some id
        | _ -> None
  ) in

  let strings = Hashtbl.create 101 in
  let counter = ref 0 in
  rules |> visit_rules (function
   | STRING s -> Hashtbl.replace strings s true
   | _ -> ());
  let strings = Common.hashset_to_list strings in

  let env = {
    tokens = Common.hashset_of_list tokens;
    start;
  } in

  pr "%token <unit> EOF\n";
  tokens |> List.iter (fun id ->
    pr (spf "%%token <unit> %s\n" (id_to_token id))
  );
  strings |> List.iter (fun s ->
      incr counter;
      pr (spf "%%token <unit> %s \"%s\"\n"
           (spf "X%d" !counter) s);
  );

  pr "\n";
  pr (spf "%%start <unit> %s\n" start);
  pr "%%\n\n";

  rules |> List.iter (fun (id, body) ->
   if is_token env id
   then ()
   else begin
     symbol env id;
     pr ": ";
     rule_body id env body;
     pr "\n";
     pr "\n";
   end
 )
