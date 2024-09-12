#
# Build support for the programming languages listed in this folder.
#
# ocaml-tree-sitter must have been built and installed for this to work.
#

# List of languages matching a tree-sitter-* repo.
#
# For example, both typescript and tsx are provided by tree-sitter-typescript.
# The list below only shows typescript, not tsx.
# For similar reasons we list sfapex here, and not apex.
#
# *** You must also add any new language to the list of languages
#     in /.circleci/config.yml for the CI tests to run for that language.
#
SUPPORTED_TS_LANGUAGES = \
  bash \
  c \
  cairo \
  clojure \
  circom \
  cpp \
  c-sharp \
  dart \
  dockerfile \
  elixir \
  fsharp \
  go \
  hack \
  haskell \
  hcl \
  html \
  java \
  javascript \
  jsonnet \
  julia \
  kotlin \
  lua \
  make \
  move-on-aptos \
  move-on-sui \
  ocaml \
  php \
  promql \
  proto \
  python \
  ql \
  r \
  ruby \
  rust \
  sfapex \
  sml \
  solidity \
  sqlite \
  swift \
  typescript \
  vue

# List of all language variants, as they're made available to semgrep.
#
# This includes all language variants e.g. typescript and tsx that may
# come from the same tree-sitter project.
# Here we list apex, and not sfapex
#
# After updating this list, run 'make links' and update the
# list of languages in the release readme (/doc/release.md).
# (nothing bad will happen if you forget, though)
#
SUPPORTED_DIALECTS = \
  apex \
  bash \
  c \
  clojure \
  cpp \
  c-sharp \
  dart \
  dockerfile \
  elixir \
  fsharp \
  go \
  hack \
  hcl \
  html \
  java \
  julia \
  javascript \
  jsonnet \
  julia \
  kotlin \
  lua \
  make \
  move-on-aptos \
  move-on-sui \
  ocaml \
  php \
  promql \
  proto \
  python \
  ql \
  r \
  ruby \
  rust \
  solidity \
  sqlite \
  swift \
  tsx \
  typescript \
  vue

# Languages which are set up to run parsing stats. Ideally, this is all
# the supported languages. See the 'stat' target.
# update: we split the list in 2 (STAT_LANGUAGES1 and STAT_LANGUAGES2) because
# running all languages in CI takes more than 3h which is the performance-plan limit.
# alt: parse languages in parallel, like we do in semgrep/stats/parsing-stats/
STAT_LANGUAGES1 = \
  bash \
  c \
  cairo \
  cpp \
  c-sharp \
  dockerfile \
  elixir \
  go \
  hack \
  haskell \
  hcl \
  java \
  javascript \
  julia \
  kotlin

STAT_LANGUAGES2 = \
  apex \
  lua \
  ocaml \
  php \
  promql \
  python \
  r \
  ruby \
  rust \
  solidity \
  tsx \
  typescript

STAT_LANGUAGES = $(STAT_LANGUAGES1) $(STAT_LANGUAGES2)

# Build and test each language. Does not run parsing stats (see 'stat:').
#
# This takes a while and is intended for CI. If you're working on a single
# language, better just run ./test-lang.
#
.PHONY: test
test:
	set -e; \
        failed=""; \
	for lang in $(SUPPORTED_TS_LANGUAGES); do \
          ./test-lang $$lang || failed="$$failed $$lang"; \
        done; \
	if [ -n "$$failed" ]; then \
	  echo "*** Failed to build or test the following languages:$$failed"; \
	  exit 1; \
	fi

.PHONY: release
release:
	@echo "'make release' is no longer supported so as to avoid"
	@echo "accidentally pushing changes for other languages."
	@echo "- If you really want to publish changes for all languages,"
	@echo "  use 'make release-all'."
	@echo "- If you want to release just one language named 'foo', run:"
	@echo ""
	@echo "    ./release foo"
	@echo ""
	exit 1

# Place the generated files into their own repo, to be used by an external
# repo as a submodule.
#
.PHONY: release-all
release-all:
	$(MAKE) -C semgrep-grammars
	set -eu; \
        for lang in $(SUPPORTED_DIALECTS); do \
	  ./release $$lang; \
	done

# Make a pretend release.
.PHONY: dry
dry:
	$(MAKE) -C semgrep-grammars
	set -eu; \
        for lang in $(SUPPORTED_DIALECTS); do \
	  ./release $$lang --dry-run; \
	done

.PHONY: stat
stat:
	$(MAKE) stat1
	$(MAKE) stat2

# Run parsing stats for each language.
# Each needs a list of projects (projects.txt) and file extensions
# (extensions.txt).
#
.PHONY: stat1
stat1:
	set -eu; \
	for lang in $(STAT_LANGUAGES1); do $(MAKE) -C $$lang stat; done
	../scripts/report-stat $(STAT_LANGUAGES1) | tee stat.txt
	test -s stat.txt  # check that the pipeline above didn't fail

.PHONY: stat2
stat2:
	set -eu; \
	for lang in $(STAT_LANGUAGES2); do $(MAKE) -C $$lang stat; done
	../scripts/report-stat $(STAT_LANGUAGES2) | tee stat.txt
	test -s stat.txt  # check that the pipeline above didn't fail

# Run stats on projects-priv.txt instead of projects.txt.
.PHONY: stat-priv
stat-priv:
	set -e; \
	for lang in $(STAT_LANGUAGES); do $(MAKE) -C $$lang stat-priv; done
	../scripts/report-stat $(STAT_LANGUAGES) | tee stat.txt

.PHONY: clean
clean:
	set -e; \
	for lang in $(SUPPORTED_DIALECTS); do $(MAKE) -C $$lang clean; done

# Helpers for github PRs using git and hub command-line tools
.PHONY: pr
pr:
	git push origin `git rev-parse --abbrev-ref HEAD`
	hub pull-request -b main

.PHONY: push
push:
	git push origin `git rev-parse --abbrev-ref HEAD`

# This force-delete looks dangerous.
# What is this for and how can everyone benefit from it?
#.PHONY: merge
#merge:
#	A=`git rev-parse --abbrev-ref HEAD` && git checkout main && git pull &&# git branch -D $$A

# Regenerate the language list in the release readme (/docs/release.md)
.PHONY: links
links:
	for x in $(SUPPORTED_DIALECTS); do \
	  echo "* [$$x](https://github.com/returntocorp/semgrep-$$x)"; \
	done | sort -u
