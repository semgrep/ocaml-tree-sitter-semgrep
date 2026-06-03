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

1. Make sure you have at least 6 GiB of free memory. More will be
   needed for some of the grammars.
2. Install the following tools:
   * git
   * GNU make
   * pkg-config: manages the installation of tree-sitter's runtime library
   * Node.js: JavaScript interpreter used to translate a grammar to json
   * cargo: Rust compiler used to build `tree-sitter`
   * [opam](https://opam.ocaml.org/doc/Install.html): OCaml package manager
3. Run `opam init`, `opam switch create 4.12.0` to install a recent
   version of OCaml.
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
language](https://semgrep.dev/docs/contributing/updating-a-grammar/).

### tree-sitter ABI 15

Each grammar is generated with the tree-sitter version pinned for it in
`lang/languages-<version>` / `lang/language-variants-<version>`, and the
generated parser's ABI is chosen automatically:

| Condition | ABI |
|--|--|
| Grammar ships a `tree-sitter.json` **and** `SEMGREP_ENABLE_ABI15` is set | 15 |
| tree-sitter >= 0.24.0 (otherwise) | 14 |
| older tree-sitter | `--no-bindings` (no ABI flag) |

ABI 15 is **off by default**: the tooling can already produce it, but we
are not yet ready to ship ABI 15 parsers. To opt in for a build, set the
environment variable:

```
SEMGREP_ENABLE_ABI15=1 make -C lang/semgrep-grammars/src build
# or for a single language:
SEMGREP_ENABLE_ABI15=1 ./lang/test-lang php
```

Accepted truthy values: `1`, `true`, `yes`, `on` (case-insensitive).
When enabled, the grammar must be pinned to a tree-sitter >= 0.25.0; the
build fails with a clear error otherwise.

### Adding a new language

See [How to add support for a new language](https://semgrep.dev/docs/contributing/adding-a-language/).

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
