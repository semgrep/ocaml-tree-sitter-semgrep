ocaml-tree-sitter-semgrep
==

[![CircleCI](https://circleci.com/gh/returntocorp/ocaml-tree-sitter-semgrep.svg?style=svg)](https://circleci.com/gh/returntocorp/ocaml-tree-sitter-semgrep)

Generate OCaml parsers based on
[tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars,
for [semgrep](https://github.com/returntocorp/semgrep).

Related ocaml-tree-sitter repositories:
* [ocaml-tree-sitter-core](https://github.com/returntocorp/ocaml-tree-sitter-core): provides the code generator that
  takes a tree-sitter grammar and produces an OCaml library from it.
* [ocaml-tree-sitter-languages](https://github.com/returntocorp/ocaml-tree-sitter-languages): community repository that has scripts
  for building and publishing OCaml libraries for parsing a variety of
  programming languages.
* **ocaml-tree-sitter-semgrep**: this repo; same as
  ocaml-tree-sitter-languages but extends each language with
  constructs specific to
  [semgrep](https://github.com/returntocorp/semgrep) patterns.

Contributing
--

### Development setup

1. Make sure you have at least 6 GiB of free memory.
2. Install [opam](https://opam.ocaml.org/doc/Install.html), git, make, pkg-config, [libtree-sitter-dev](https://github.com/returntocorp/ocaml-tree-sitter-core/blob/main/scripts/install-tree-sitter-lib), nodejs, npm.
3. Run `opam init`, `opam switch create 4.12.0` to install a recent OCaml.
4. Install [ocaml dev tools for your favorite
   editor](https://github.com/janestreet/install-ocaml):
   typically `opam install merlin` + some plugin for your editor.
5. Install `pre-commit` with `pip3 install pre-commit` and run
   `pre-commit install` to set up the pre-commit hook.
   This will re-indent code in a consistent fashion each time you call
   `git commit`.
6. Check out the [extra instructions for MacOS](https://github.com/returntocorp/ocaml-tree-sitter-core/blob/main/doc/macos.md).

See the Makefile for the available targets. Get started with:
```
make update
make setup
```

Then build and install the OCaml code generator (core):
```
make && make install
```

### Testing a language

Say you want to build and test support for kotlin, you would run this:

```
$ cd lang
$ ./test-lang kotlin
```

For details, see [How to upgrade the grammar for a
language](doc/updating-a-grammar.md).

### Adding a new language

See [How to add support for a new language](doc/adding-a-language.md).

Documentation
--

We have limited [documentation](doc) which is mostly targeted at
early contributors. It's growing organically based on demand, so don't
hesitate to [file an issue](https://github.com/returntocorp/ocaml-tree-sitter/issues)
explaining what you're trying to do.

License
--

ocaml-tree-sitter is free software with contributors from multiple
organizations. The project is driven by [r2c](https://github.com/returntocorp).

- OCaml code developed specifically for this project is
  distributed under the terms of the [GNU GPL v3](LICENSE).
- The OCaml bindings to tree-sitter's C API were created by Bryan
  Phelps as part of the reason-tree-sitter project.
- The tree-sitter grammars for major programming languages are
  external projects. Each comes with its own license.
