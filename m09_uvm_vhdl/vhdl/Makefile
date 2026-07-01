# Makefile — Module 09: VHDL UART + mixed-language xsim
#
# Invoke from m09_uvm_vhdl/vhdl/:
#   cd ~/future_prep/m09_uvm_vhdl/vhdl && make all
#
# Targets:
#   make all    — compile VHDL DUT + SV testbench, elaborate, run
#   make clean  — remove build artifacts and VCDs
#
# Prerequisites:
#   source ~/future_prep/scripts/activate_qprep.sh
#
# Mixed-language flow: xvhdl compiles the VHDL sources, xvlog compiles the
# SV testbench — both into the same "work" library — then xelab links
# across the language boundary. See tb_uart_mixed.sv for the VHDL<->SV
# cheat-sheet this exercise is built around.

WAVES_DIR := ../../waves
WAVES_ABS := $(abspath $(WAVES_DIR))
BUILD_DIR := build

.PHONY: all clean check_dirs

all: check_dirs
	@echo "--- [xvhdl] uart_tx.vhd, uart_rx.vhd ---"
	cd $(BUILD_DIR) && xvhdl ../uart_tx.vhd ../uart_rx.vhd 2>&1 | grep -E "ERROR|WARNING"; \
	echo "--- [xvlog] tb_uart_mixed.sv ---"; \
	xvlog --sv ../tb_uart_mixed.sv 2>&1 | grep -E "ERROR|WARNING"; \
	echo "--- [xelab] ---"; \
	xelab tb_uart_mixed -s uart_snap 2>&1 | grep -E "ERROR|Built|WARNING"; \
	echo "--- [xsim] ---"; \
	xsim uart_snap --testplusarg 'DUMPFILE=$(WAVES_ABS)/m09_uart_mixed.vcd' --runall 2>&1 | grep -E "PASS|FAIL|ERROR"
	@echo ""
	@echo "============================================"
	@echo " M09 VHDL: MIXED-LANGUAGE RUN COMPLETE"
	@echo " VCD in $(WAVES_DIR)/m09_uart_mixed.vcd"
	@echo "============================================"

check_dirs:
	@mkdir -p $(BUILD_DIR) $(WAVES_DIR)

clean:
	rm -rf $(BUILD_DIR)
	rm -f $(WAVES_DIR)/m09_uart_mixed.vcd
	@echo "Cleaned."
