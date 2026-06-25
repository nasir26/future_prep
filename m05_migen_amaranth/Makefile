SHELL   := bash
PYTHON  := python
PYTEST  := $(PYTHON) -m pytest
WAVES   := $(HOME)/future_prep/waves

.PHONY: all test migen amaranth vcd clean

all: test vcd

# ── Run all tests ────────────────────────────────────────────────────────────
test: migen amaranth

migen:
	$(PYTEST) tests/test_migen.py -v

amaranth:
	$(PYTEST) tests/test_amaranth.py -v

# ── Generate VCD waveforms ───────────────────────────────────────────────────
vcd:
	@mkdir -p $(WAVES)
	$(PYTHON) rtl/ex01_migen_basics.py
	$(PYTHON) rtl/ex02_amaranth_basics.py
	$(PYTHON) rtl/ex03_migen_fifo.py
	$(PYTHON) rtl/ex04_amaranth_fifo.py
	$(PYTHON) rtl/ex05_amaranth_dds.py

# ── Verilog export (Amaranth → Yosys → Verilog) ─────────────────────────────
verilog:
	$(PYTHON) -c "from rtl.ex02_amaranth_basics import elaborate_to_verilog; \
	              elaborate_to_verilog('rtl/counter_gen.v'); print('counter_gen.v written')"
	$(PYTHON) -c "from rtl.ex04_amaranth_fifo import elaborate_to_verilog; \
	              elaborate_to_verilog('rtl/fifo_gen.v');    print('fifo_gen.v written')"
	$(PYTHON) -c "from rtl.ex05_amaranth_dds  import elaborate_to_verilog; \
	              elaborate_to_verilog('rtl/dds_gen.v');     print('dds_gen.v written')"

clean:
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f rtl/*.v
