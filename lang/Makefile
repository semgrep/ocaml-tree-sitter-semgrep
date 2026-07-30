#
# Build support for the programming languages listed in this folder.
#
# ocaml-tree-sitter must have been built and installed for this to work.
#

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
  c-sharp-pro \
  dockerfile \
  elixir \
  fga \
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
  cfml \
  gosu \
  lua \
  move-on-sui \
  ocaml \
  php \
  powershell \
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
# Takes a while: for a single language, run ./test-lang instead. The language
# list is the same one .github/workflows/test-languages.yml uses for its matrix.
#
.PHONY: test
test:
	../core/scripts/provision-tree-sitter-all
	set -e; \
        failed=""; \
	for lang in $$(scripts/list-languages); do \
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


# Every language variant, including several from one tree-sitter project (e.g.
# typescript and tsx), and apex rather than sfapex.
#
# After editing language-variants-*, run 'make links' and update the language
# list in the release readme (/doc/release.md) — nothing breaks if you forget.
SUPPORTED_DIALECTS := $(shell cat language-variants-* | sort -u)

# Print the language list for the release readme (/doc/release.md).
# Does not write the file — paste the output into the Appendix section.
.PHONY: links
links:
	for x in $(SUPPORTED_DIALECTS); do \
	  echo "* [$$x](https://github.com/returntocorp/semgrep-$$x)"; \
	done | sort -u
