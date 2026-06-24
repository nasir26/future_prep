# M02 cocotb — Makefile
# Prereq: conda activate qprep  (or source ../scripts/activate_qprep.sh)
#
# Targets
# -------
#   make              → run all three test suites (counter + axis + rand)
#   make test_counter → ex01: hello cocotb basics
#   make test_axis    → ex02: AXI-Stream FIFO directed (Driver/Monitor/Scoreboard)
#   make test_rand    → ex03: AXI-Stream FIFO constrained-random + coverage
#   make clean        → remove all build artifacts

PYTHON := python
RUNNER := tests/run_sim.py

.PHONY: all test_counter test_axis test_rand clean

all: test_counter test_axis test_rand
	@echo ""
	@echo "=== M02 cocotb: all suites PASS ==="

test_counter:
	@echo "--- ex01: hello cocotb (4-bit counter) ---"
	$(PYTHON) $(RUNNER) counter

test_axis:
	@echo "--- ex02: AXI4-Stream FIFO — Driver/Monitor/Scoreboard ---"
	$(PYTHON) $(RUNNER) axis

test_rand:
	@echo "--- ex03: AXI4-Stream FIFO — constrained-random + coverage ---"
	$(PYTHON) $(RUNNER) rand

clean:
	rm -rf build/
	@echo "M02 build artifacts removed."
