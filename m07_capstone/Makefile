################################################################################
# M07 Capstone — Makefile
# Stack: Python 3.11 / QuTiP 5 / asyncio / openqasm3 (regex subset)
# Depends on: M06 iontrap_emu (sibling directory)
################################################################################

PYTHON   := python3
M06      := ../m06_iontrap_emu
PYTEST_FLAGS := -v --tb=short

# Add both the module root and M06 to PYTHONPATH so `import qpu` and
# `import iontrap` resolve without installing either package.
PYPATH := $(M06):.

.PHONY: all test demo clean

all: test

test:
	PYTHONPATH=$(PYPATH) $(PYTHON) -m pytest tests/ $(PYTEST_FLAGS)

demo: demo-bell demo-rabi

demo-bell:
	@echo "=== Bell circuit ==="
	PYTHONPATH=$(PYPATH) $(PYTHON) run_qasm3.py circuits/bell.qasm --shots 500

demo-rabi:
	@echo "=== Rabi (X gate) circuit ==="
	PYTHONPATH=$(PYPATH) $(PYTHON) run_qasm3.py circuits/rabi.qasm --shots 500

clean:
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	find . -name '.pytest_cache' -type d -exec rm -rf {} + 2>/dev/null || true
