PYTHON := python
RUNNER := tests/run_sim.py

.PHONY: all test_dds test_envelope test_sequencer test_rabi clean

all: test_dds test_envelope test_sequencer test_rabi

test_dds:
	$(PYTHON) $(RUNNER) dds

test_envelope:
	$(PYTHON) $(RUNNER) envelope

test_sequencer:
	$(PYTHON) $(RUNNER) sequencer

test_rabi:
	$(PYTHON) $(RUNNER) rabi

clean:
	rm -rf build/
