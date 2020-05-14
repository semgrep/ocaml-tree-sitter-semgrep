open Common
open Ast_grammar_normalized2

type env = {
  tokens: string Common.hashset; (* the TOKEN *)
  start: string;
}

let arity simple =
  match simple with
  | ATOM _ | REPEAT _ | REPEAT1 _  | OPTION _ -> 1
  | SEQ(xs) -> List.length xs

let arity_str simple =
  let n = arity simple in
  if n = 1
  then ""
  else spf "%d" n

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
  | REPEAT x -> 
      pr (spf "list%s(" (arity_str x)); 
      simple_argument env x; 
      pr ")"
  | REPEAT1 x -> 
      pr (spf "nonempty_list%s(" (arity_str x)); 
      simple_argument env x; 
      pr ")"
  | OPTION x -> pr (spf "option%s(" (arity_str x)) ; 
      simple_argument env x; 
      pr ")"

and simple_argument env x =
  match x with
  | ATOM _ | REPEAT _ | REPEAT1 _  | OPTION _ -> simple env x
  | SEQ(xs) -> 
      let rec aux = function
        | [] -> ()
        | [x] -> 
            if arity x = 1
            then simple env x
            else begin
              pr (spf "seq%s(" (arity_str x)); 
              simple env x; 
              pr ")"
            end
        | x::xs -> simple env x; pr ", "; aux xs
      in
      aux xs


let rule_body id env x =
  match id with
  | "block" ->  pr "XXX { }"
  | "string" ->  pr "YYY { }"
  | _ -> 
  (match x with
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
  pr "%token <unit> XXX\n";
  pr "%token <unit> YYY\n";
  pr "%token <unit> ZZZ\n";
  tokens |> List.iter (fun id ->
    pr (spf "%%token <unit> %s\n" (id_to_token id))
  );
  strings |> List.iter (fun s ->
      let tok =
        match s with
        | _ when s =~ "^[a-z]+$" -> "K" ^ s
        | "+" -> "XPLUS" | "-" -> "XMINUS"
        | "*" -> "XMUL" | "/" -> "XDIV"
        | "!" -> "XBANG" | "$" -> "XDOLLAR"
        | "(" -> "XLPAR" | ")" -> "XRPAR"
        | "[" -> "XLBRACKET" | "]" -> "XRBRACKET"
        | "{" -> "XLBRACE" | "}" -> "XRBRACE"
        | "," -> "XCOMMA" | ";" -> "XSEMI"
        | "." -> "XDOT" | ":" -> "XCOLON"
        | "=" -> "XEQ"
        | "_" -> "XUNDERSCORE"
        | "|" -> "XPIPE" | "~" -> "XTILDE" | "@" -> "XAT"
        | _ -> 
           incr counter;
           spf "X%d" !counter
      in
      pr (spf "%%token <unit> %s \"%s\"\n" tok s);
  );
  pr "\n";
  pr (spf "%%start <unit> %s\n" start);
  pr "%%\n\n";

  pr "
%inline
option2(a,b):
 | { }
 | a b { }
%inline
list2(a,b): list(pair(a,b)) { }
%inline
nonempty_list2(a,b): nonempty_list(pair(a,b)) { }
";
pr "
_automatic_semicolon: ZZZ { }
";
  pr "\n";

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
