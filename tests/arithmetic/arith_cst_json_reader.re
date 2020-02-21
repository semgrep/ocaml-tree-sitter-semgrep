/* Yoann Padioleau
 *
 * Copyright (C) 2020 r2c
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License (GPL)
 * version 2 as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * file license.txt for more details.
 */
open Common;
open Ast_arithmetic;
module J = Json_type;

let error = (s, json) => failwith(spf("Wrong format: %s, got: %s",s,Json_io.string_of_json(json)));

let rec parse_expression = (json: J.json_type): expression => {
    switch(json) {
    | J.Array([
        J.Object([("type", J.String("number")),
            ("children", _)
        ])
      ]) => Intermediate_type4("number")
    | J.Array([
        J.Object([("type", J.String("expression")),
            ("children", exp1)
        ]),
        J.Object([("type", J.String(expr_str)),
            ("children", _)
        ]),
        J.Object([("type", J.String("expression")),
            ("children", exp2)
        ]),
      ]) => Intermediate_type5((parse_expression(exp1), expr_str, parse_expression(exp2)))
    | _ =>  error("Todo parse_expression", json)
    }
}

and parse_expression_statement = (json:  J.json_type): expression_statement => {
    switch(json) {
    | J.Array([
        J.Object([("type", J.String("expression")),
            ("children", expression)]),
        J.Object([("type", J.String(expr_str)),
            ("children", _)])
      ]) => (parse_expression(expression), expr_str)
    | _ => error("Todo parse_expression_statement", json)
    }
}
and parse_body = (json: J.json_type): cst_node =>
{
    switch(json) {
    | J.Object([("type", J.String("comment")),
                ("children", _)]) => Comment("comment")
    | J.Object([("type", J.String("number")),
                ("children", _)]) => Number("number")
    | J.Object([("type", J.String("variable")),
                ("children", _)]) => Variable("variable")
    | J.Object([("type", J.String("expression_statement")),
                ("children", xs)]) => Expression_statement(parse_expression_statement(xs))
    | J.Object([("type", J.String("ERROR")),
                ("children", _)]) => Comment("HOW TO HANDLE THIS ERROR?")
    | _ =>  error("Todo general", json)
    };
}

and parse_children = (xs: J.json_type): list(cst_node) => {
    switch(xs) {
    | J.Array(xs) => List.map(parse_body, xs)
    | _ => error("Top parse_children", xs)
    }
}

/*****************************************************************************/
/* Entrypoint */
/*****************************************************************************/
let parse = (file): program_cst => {
    let json = Json_io.load_json(file);
    switch(json) {
    | J.Object(xs) => {
      let children = List.assoc("children",xs);
      parse_children(children)
    }
    | _ => error("Toplevel", json);
    }
}

