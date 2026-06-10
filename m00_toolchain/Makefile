# Makefile — Module 00 smoke tests
#
# ALL targets must be invoked from this directory (m00_toolchain/).
#   cd ~/future_prep/m00_toolchain && make smoke
#
# Targets:
#   make smoke         — run all three simulators, produce VCDs in ../waves/
#   make sim_icarus    — Icarus Verilog only
#   make sim_xsim      — Xilinx xsim only  (requires setup_vivado.sh)
#   make sim_verilator — Verilator only
#   make clean         — remove build artifacts and VCDs
#
# Prerequisites (all in the qprep conda env):
#   iverilog, vvp, verilator, g++
# Plus Vivado 2023.2 on PATH for xsim targets.
# One-line setup:  source ~/future_prep/scripts/activate_qprep.sh

WAVES_DIR  := ../waves
RTL_DIR    := rtl
BUILD_DIR  := build

COUNTER_SRC := $(RTL_DIR)/counter.v

# Icarus settings
ICARUS_TB  := $(RTL_DIR)/tb_counter_icarus.v
ICARUS_VVP := $(BUILD_DIR)/counter_icarus.vvp

# xsim settings — runs from BUILD_DIR/xsim_work/; VCD path in TB is ../../../waves/
XSIM_TB    := $(RTL_DIR)/tb_counter_xsim.v
XSIM_SNAP  := counter_xsim_snap
XSIM_DIR   := $(BUILD_DIR)/xsim_work

# Verilator settings
VLTR_TB    := $(RTL_DIR)/tb_counter_verilator.cpp
VLTR_DIR   := $(BUILD_DIR)/verilator_obj
VLTR_BIN   := $(VLTR_DIR)/Vcounter

.PHONY: smoke sim_icarus sim_xsim sim_verilator clean check_dirs

# ============================================================
# Top-level smoke target
# ============================================================
smoke: check_dirs sim_icarus sim_xsim sim_verilator
	@echo ""
	@echo "============================================"
	@echo " ALL SMOKE TESTS PASSED"
	@echo " VCD waveform files:"
	@ls -lh $(WAVES_DIR)/counter_*.vcd 2>/dev/null || echo "  (check paths)"
	@echo "============================================"
	@echo " Open in VS Code: install 'Surfer' extension"
	@echo " then Ctrl+Shift+P → 'Surfer: Open VCD file'"
	@echo " or right-click any .vcd in Explorer → 'Open With Surfer'"

check_dirs:
	@mkdir -p $(BUILD_DIR) $(WAVES_DIR)

# ============================================================
# Icarus Verilog
# VCD written to ../waves/counter_icarus.vcd (relative to m00_toolchain/)
# ============================================================
sim_icarus: check_dirs
	@echo "--- [1/3] Icarus Verilog ---"
	iverilog -g2001 -o $(ICARUS_VVP) $(COUNTER_SRC) $(ICARUS_TB)
	vvp $(ICARUS_VVP)
	@ls -lh $(WAVES_DIR)/counter_icarus.vcd && echo "VCD OK"

# ============================================================
# Xilinx xsim
# Runs from BUILD_DIR/xsim_work/ — VCD path in TB is ../../../waves/
# Requires: source ~/future_prep/scripts/setup_vivado.sh
# ============================================================
sim_xsim: check_dirs
	@echo "--- [2/3] xsim ---"
	@mkdir -p $(XSIM_DIR)
	cd $(XSIM_DIR) && \
	  xvlog $(abspath $(COUNTER_SRC)) $(abspath $(XSIM_TB)) 2>&1 | grep -E "ERROR|analyzing|Built" ; \
	  xelab tb_counter_xsim -s $(XSIM_SNAP) 2>&1 | grep -E "ERROR|Built" ; \
	  xsim $(XSIM_SNAP) --runall 2>&1 | grep -E "PASS|FAIL|ALL|ERROR|finish"
	@ls -lh $(WAVES_DIR)/counter_xsim.vcd && echo "VCD OK"

# ============================================================
# Verilator
# Binary run from m00_toolchain/ so VCD path ../waves/ resolves correctly
# ============================================================
sim_verilator: check_dirs
	@echo "--- [3/3] Verilator ---"
	verilator --cc --exe --trace --build \
	  -Mdir $(VLTR_DIR) \
	  $(abspath $(COUNTER_SRC)) $(abspath $(VLTR_TB)) \
	  -CFLAGS "-std=c++14" 2>&1 | grep -E "Verilat|Error"
	$(VLTR_BIN)
	@ls -lh $(WAVES_DIR)/counter_verilator.vcd && echo "VCD OK"

# ============================================================
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(WAVES_DIR)/counter_*.vcd
	@echo "Cleaned."
