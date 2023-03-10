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
