open Common
module A = Ast_grammar
module B = Ast_grammar_normalized2

let counter = ref 0

let gensym () = 
  incr counter; 
  "intermediate" ^ (string_of_int (!counter))

let rec normalize_to_simple (body : A.rule_body) =
   match body with
   | A.TOKEN |A.IMMEDIATE_TOKEN | A.BLANK 
   | A.SYMBOL _ | A.STRING _| A.PATTERN _ ->
       let (atom, rest) = normalize_to_atom body in
       (B.ATOM atom, rest)
   | A.SEQ (bodies) ->
       let xs = List.map normalize_to_simple bodies in
       let atoms = List.map fst xs in
       let intermediates = List.flatten (List.map snd xs) in
       (B.SEQ atoms, intermediates)

   | A.REPEAT (body) ->
       let (simple, rest) = normalize_to_simple body in
       (B.REPEAT simple, rest)
   | A.REPEAT1 (body) ->
       let (simple, rest) = normalize_to_simple body in
       (B.REPEAT1 simple, rest) 
   (* some CHOICES are really OPTION *)
   | A.CHOICE bodies ->
       (match choice_bodies bodies with
       | Left (x, rest) -> x, rest
       | Right (_x, _rest) ->
         let fresh_ident = gensym () in
         (B.ATOM (B.SYMBOL fresh_ident), [(fresh_ident, body)])
       )

   | _ ->
       let fresh_ident = gensym () in
       (B.ATOM (B.SYMBOL fresh_ident), [(fresh_ident, body)])

and normalize_to_atom (body : A.rule_body) =
   match body with
   | A.TOKEN | A.IMMEDIATE_TOKEN | A.BLANK | A.PATTERN _ -> 
      (B.TOKEN, [])
   | A.STRING string ->
       (B.STRING string, [])
   | A.SYMBOL name ->
       (B.SYMBOL name, [])
   | _ ->
       let fresh_ident = gensym () in
       (B.SYMBOL fresh_ident, [(fresh_ident, body)])


and choice_bodies bodies = 
   match List.rev bodies with
   | (A.BLANK)::[] -> failwith "Impossible, a single BLANK in a CHOICE"
   | (A.BLANK)::other_body::[] ->
       let (simple, rest) = normalize_to_simple other_body in
       Left ((B.OPTION simple), rest)
   | (A.BLANK)::other_bodies ->
       let (simple, rest) = normalize_to_simple (A.CHOICE other_bodies) in
       Left  (((B.OPTION simple), rest))
   | _ ->
       let xs = List.map normalize_to_simple bodies in
       let simples = List.map fst xs in
       let intermediates = List.flatten (List.map snd xs) in
       Right (B.CHOICE simples, intermediates)

and normalize_body (rule_body : A.rule_body) =
   match rule_body with
   | A.IMMEDIATE_TOKEN | A.TOKEN | A.SYMBOL _ | A.STRING _ | A.PATTERN _
   | A.BLANK
   | A.SEQ _ | A.REPEAT _ | A.REPEAT1 _ ->
       let (simple, rest) = normalize_to_simple rule_body in
       (B.SIMPLE simple, rest)
   | A.CHOICE bodies ->
       (match choice_bodies bodies with
       | Left (x, rest) -> B.SIMPLE x, rest
       | Right (x, rest) -> x, rest
       )
   | A.ALIAS (body, _) ->
       let (simple, rest) = normalize_to_simple body in
       (B.SIMPLE simple, rest)


and normalize_rule ((name, rule_body) : A.rule) =
  let (this_body, intermediates) = normalize_body rule_body in
  let this_rule = (name, this_body) in
  if intermediates = []
  then [this_rule]
  else
    let other_rules = List.flatten (List.map normalize_rule intermediates) in
    this_rule :: other_rules

let normalize_rules (xs : A.rule list) =
  List.flatten (List.map normalize_rule xs)

let normalize ((name, rules) : A.grammar) =
  (name, (normalize_rules rules))
