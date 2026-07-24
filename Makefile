#
# Build and install code generators and runtime support for generated parsers.
#
# Building and installing support for specific programming languages is done in
# a second phase, in lang/
#

PROJECT_ROOT = $(shell pwd)

# The ocaml-tree-sitter code generator now builds with dune (see core/). The
# dune build promotes it to core/bin/ocaml-tree-sitter, where the per-language
# builds in lang/ look for it (lang/Makefile.common: OCAML_TREE_SITTER_BINDIR).
.PHONY: build
build:
	cd core && dune build bin/ocaml-tree-sitter

# Full development setup.
.PHONY: setup
setup:
	opam install --deps-only -y ./core
	$(MAKE) build

# Shortcut for updating the git submodules.
.PHONY: update
update:
	git submodule update --init --recursive --depth 1

.PHONY: clean
clean:
	rm -rf bin
	make -C lang clean

.PHONY: distclean
distclean:
	# remove everything that's git-ignored
	git clean -dfX

# Run core tests
.PHONY: test
test: build
	cd core && dune runtest
	@echo
	@echo '=================================================================='
	@echo '"make test" ran the core (OCaml) tests only.'
	@echo 'To also run the Python / ABI tests (not covered here), run:'
	@echo '  make setup-tree-sitter-versions   # install every pinned tree-sitter version'
	@echo '  make test-python                  # pytest: version resolution, grammar pins, ABI gating, update-grammar'
	@echo '=================================================================='

# Run the Python test suites (not run by 'make test'). For full coverage, the
# pinned tree-sitter versions must be installed ('make setup-tree-sitter-versions').
# Uses the 'pytest' on PATH if present, otherwise falls back to 'python3 -m pytest'.
PYTHON_TESTS = lang/test_grammar_ts_version.py lang/test_ts_versions.py lang/test_abi15_gating.py scripts/test_update_grammar.py scripts/test_propose_grammar_update.py
.PHONY: test-python
test-python:
	@if command -v pytest >/dev/null 2>&1; then \
	  pytest $(PYTHON_TESTS); \
	else \
	  python3 -m pytest $(PYTHON_TESTS); \
	fi

# Install every tree-sitter version the grammars are pinned to (derived from the
# lang/languages-* files), each into its own core/tree-sitter-<version>/. Needed
# by the per-language builds and the Python tests. Driven by dune (see the
# 'tree-sitter-versions' alias in core/dune); idempotent.
.PHONY: setup-tree-sitter-versions
setup-tree-sitter-versions:
	cd core && dune build tree-sitter-versions.stamp

# Build and test all the production languages.
.PHONY: lang
lang: build
	$(MAKE) -C lang

# Run parsing stats for the supported languages in lang/.
.PHONY: stat
stat:
	$(MAKE) -C lang
	$(MAKE) -C lang stat

# ugly: but split make stat in 2 to pass the 3h CI limit
.PHONY: stat1
stat1:
	$(MAKE) -C lang
	$(MAKE) -C lang stat1

.PHONY: stat2
stat2:
	$(MAKE) -C lang
	$(MAKE) -C lang stat2

# Install core's OCaml libraries (tree-sitter.run/.bindings/.gen) and the
# tree-sitter runtime into the current opam switch. The per-language builds in
# lang/ are standalone dune projects that resolve tree-sitter.run via findlib,
# so this step is required before 'make lang'.
.PHONY: install
install:
	cd core && dune build @install
	cd core && dune install tree-sitter

# Used by Conductor at setup time
.PHONY: agent-setup
agent-setup: update setup build install
	pre-commit install
