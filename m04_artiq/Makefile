PYTHON  := python
PYTEST  := pytest

.PHONY: all test clean

all: test

test:
	$(PYTEST) tests/ -v --tb=short

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
