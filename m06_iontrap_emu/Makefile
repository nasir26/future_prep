SHELL  := bash
PYTHON := python
PYTEST := $(PYTHON) -m pytest

.PHONY: all test clean

all: test

test:
	$(PYTEST) tests/ -v

test-fast:
	$(PYTEST) tests/test_noise.py tests/test_readout.py tests/test_cooling.py -v

clean:
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
