#
# Build and install code generators and runtime support for generated parsers.
#
# Building and installing support for specific programming languages is done in
# a second phase, in lang/
#

PROJECT_ROOT = $(shell pwd)

.PHONY: build
build:
	cd core && ./configure
	$(MAKE) -C core build

# Full development setup.
.PHONY: setup
setup:
	cd core && ./configure
	$(MAKE) -C core setup

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
	$(MAKE) -C core test
	@echo
	@echo '=================================================================='
	@echo '"make test" ran the core (OCaml) tests only.'
	@echo 'To also run the Python / ABI tests (not covered here), run:'
	@echo '  make setup-tree-sitter-versions   # install every pinned tree-sitter version'
	@echo '  make test-python                  # pytest: grammar version + update-grammar'
	@echo '  ./lang/scripts/test-abi15-gating  # ABI 15 gating test'
	@echo '=================================================================='

# Run the Python test suites (not run by 'make test'). Requires pytest and, for
# full coverage, the pinned tree-sitter versions ('make setup-tree-sitter-versions').
.PHONY: test-python
test-python:
	@python3 -c 'import pytest' 2>/dev/null \
	  || { echo "pytest is not installed: pip install pytest"; exit 1; }
	python3 -m pytest lang/test_grammar_ts_version.py scripts/test_update_grammar.py

# Install every tree-sitter version the grammars are pinned to (derived from the
# lang/languages-* files), each into its own core/tree-sitter-<version>/. Needed
# by the per-language builds and the Python tests. Restores the previously
# selected version at the end.
.PHONY: setup-tree-sitter-versions
setup-tree-sitter-versions:
	@set -eu; \
	saved=$$(cat core/tree-sitter-version 2>/dev/null || cat core/tree-sitter-version.default); \
	for v in $$(lang/scripts/ts-versions); do \
	  echo ">>> Installing tree-sitter $$v"; \
	  ( cd core && ./scripts/switch-tree-sitter-version "$$v" \
	      && ./scripts/install-tree-sitter-cli \
	      && ./scripts/install-tree-sitter-lib ); \
	done; \
	echo ">>> Restoring tree-sitter $$saved"; \
	( cd core && ./scripts/switch-tree-sitter-version "$$saved" >/dev/null )

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

.PHONY: install
install:
	$(MAKE) -C core install

# Used by Conductor at setup time
.PHONY: agent-setup
agent-setup: update setup build install
	pre-commit install
