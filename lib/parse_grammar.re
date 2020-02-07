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
open Core;
module Y = Yojson;
module G = Grammar_j;
module G_t = Grammar_t;

/*****************************************************************************/
/* Entrypoint */
/*****************************************************************************/
let parse = (filename) => {
  let json = In_channel.read_all(filename);
  let _grammar = G.grammar_of_string(json);
  /* let message =
    switch (grammar) {
    | _ => "adai"
    };
  print_endline(message); */
  raise(Todo);
};