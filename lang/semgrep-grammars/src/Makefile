PROJECT_ROOT = $(shell git rev-parse --show-toplevel)

# Generate parsers for the semgrep-* packages.
.PHONY: build
build:
	set -e; \
	for pkg in semgrep-* ; do \
	  echo "Build $$pkg"; \
	  $(MAKE) -C $$pkg build; \
	done

# Test the semgrep-* packages.
.PHONY: test
test:
	set -e; \
	for pkg in semgrep-* ; do \
	  echo "Test $$pkg"; \
	  $(MAKE) -C $$pkg test; \
	done

.PHONY: clean
clean:
	git clean -dfX
