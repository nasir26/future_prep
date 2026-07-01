# Makefile — Module 09: UVM testbench (AXI4-Stream FIFO)
#
# Invoke from m09_uvm_vhdl/uvm/:
#   cd ~/future_prep/m09_uvm_vhdl/uvm && make all
#
# Targets:
#   make smoke   — axis_smoke_test: one packet, consumer always ready
#   make random  — axis_random_test: 20 random-length packets, randomized backpressure
#   make all     — both tests
#   make clean   — remove build artifacts and VCDs
#
# Prerequisites:
#   source ~/future_prep/scripts/activate_qprep.sh
#
# The DUT (axi_stream_fifo.sv) is compiled straight out of m01_sv_sva/rtl/ —
# see tb_top.sv for why this is a reference, not a copy.

WAVES_DIR := ../../waves
WAVES_ABS := $(abspath $(WAVES_DIR))
BUILD_DIR := build

SRCS := axis_if.sv axis_pkg.sv ../../m01_sv_sva/rtl/axi_stream_fifo.sv tb_top.sv

.PHONY: all smoke random clean check_dirs

all: smoke random
	@echo ""
	@echo "============================================"
	@echo " M09 UVM: ALL TESTS COMPLETE"
	@echo " VCDs in $(WAVES_DIR)/m09_uvm_*.vcd"
	@echo "============================================"

check_dirs:
	@mkdir -p $(BUILD_DIR) $(WAVES_DIR)

# One elaborated snapshot serves both tests — +UVM_TESTNAME picks the test
# class at run time, so there's no need to re-elaborate per test.
$(BUILD_DIR)/.elab: check_dirs $(SRCS)
	@mkdir -p $(BUILD_DIR)
	cd $(BUILD_DIR) && \
	  xvlog --sv -L uvm $(addprefix ../,$(SRCS)) 2>&1 | grep -vE "^$$|^Vivado" ; \
	  xelab -L uvm tb_top -s uvm_snap --timescale 1ns/1ps 2>&1 | grep -E "ERROR|Built|WARNING"
	@touch $@

# Usage: $(call XSIM_UVM_RUN, test_name, vcd_basename)
define XSIM_UVM_RUN
	@echo "--- [xsim/uvm] $1 ---"
	cd $(BUILD_DIR) && \
	  xsim uvm_snap \
	    --testplusarg 'UVM_TESTNAME=$1' \
	    --testplusarg 'DUMPFILE=$(WAVES_ABS)/$(strip $2)' \
	    --runall 2>&1 | grep -E "UVM_INFO.*SCOREBOARD|UVM_ERROR|UVM_FATAL|Report counts by severity|UVM_(INFO|WARNING|ERROR|FATAL) :"
	@echo ""
endef

smoke: $(BUILD_DIR)/.elab
	$(call XSIM_UVM_RUN,axis_smoke_test,m09_uvm_smoke.vcd)

random: $(BUILD_DIR)/.elab
	$(call XSIM_UVM_RUN,axis_random_test,m09_uvm_random.vcd)

clean:
	rm -rf $(BUILD_DIR)
	rm -f $(WAVES_DIR)/m09_uvm_*.vcd
	@echo "Cleaned."
