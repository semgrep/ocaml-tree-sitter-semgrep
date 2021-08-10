Releasing generated code for semgrep
==

The process for updating a grammar and releasing the generated code in
described in details [in this document](updating-a-grammar.md).

Until we have an automatic process for this and for security reasons,
please ask someone at r2c to release the code for the language.

Contact channels:
* your ocaml-tree-sitter pull request
* the [r2c Slack channel #dev-discussions](https://r2c.slack.com/archives/dev-discussions/)

Step 1: Check the sources
--

Check that the external source code looks clean, including any
dependency used at build time or run time. Source code for a
tree-sitter-* grammar is:
* `grammar.js` and its dependencies. `grammar.js` should just define a
  grammar object. It should not write to the filesystem.
* `src/scanner.c` or `src/scanner.cc` if such file exists, and any
  dependency they may have. There should be no dependency other than
  the standard C or C++ libraries and tree-sitter libraries.

Step 2: Generate and push to GitHub
--

For a language `foolang`, the commands are:

```
make && make install
cd lang
./test-lang foolang
./release foolang
```

This will push to the git repository for `semgrep-foolang`, which will
then be used in semgrep as a git submodule.

Appendix: List of semgrep-* repos
--

The list of languages below should match the languages listed in the [`lang` folder of ocaml-tree-sitter-semgrep](https://github.com/returntocorp/ocaml-tree-sitter-semgrep/tree/main/lang). Let's try to keep it up-to-date.

* [bash](https://github.com/returntocorp/semgrep-bash)
* [c](https://github.com/returntocorp/semgrep-c)
* [cpp](https://github.com/returntocorp/semgrep-cpp)
* [c-sharp](https://github.com/returntocorp/semgrep-c-sharp)
* [dockerfile](https://github.com/returntocorp/semgrep-dockerfile)
* [go](https://github.com/returntocorp/semgrep-go)
* [hack](https://github.com/returntocorp/semgrep-hack)
* [hcl](https://github.com/returntocorp/semgrep-hcl)
* [html](https://github.com/returntocorp/semgrep-html)
* [java](https://github.com/returntocorp/semgrep-java)
* [javascript](https://github.com/returntocorp/semgrep-javascript)
* [kotlin](https://github.com/returntocorp/semgrep-kotlin)
* [lua](https://github.com/returntocorp/semgrep-lua)
* [ocaml](https://github.com/returntocorp/semgrep-ocaml)
* [php](https://github.com/returntocorp/semgrep-php)
* [r](https://github.com/returntocorp/semgrep-r)
* [ruby](https://github.com/returntocorp/semgrep-ruby)
* [rust](https://github.com/returntocorp/semgrep-rust)
* [sqlite](https://github.com/returntocorp/semgrep-sqlite)
* [tsx](https://github.com/returntocorp/semgrep-tsx)
* [typescript](https://github.com/returntocorp/semgrep-typescript)
* [vue](https://github.com/returntocorp/semgrep-vue)

GitHub homepage is: `https://github.com/returntocorp/semgrep-$lang`

Git URL is: `git@github.com:returntocorp/semgrep-$lang.git`
or `https://github.com/returntocorp/semgrep-$lang.git`
