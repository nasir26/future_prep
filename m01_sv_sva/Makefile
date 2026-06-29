# Makefile — Module 01: SystemVerilog + SVA
#
# Invoke from m01_sv_sva/:
#   cd ~/future_prep/m01_sv_sva && make all
#
# Targets:
#   make all         — run all ex01–ex07 exercises
#   make ex01 .. ex07 — individual exercises
#   make clean       — remove build artifacts and VCDs
#
# Simulator choice:
#   ex01–ex04: iverilog 12.0  (basic SV — always_ff/enum/typedef)
#   ex05–ex07: xsim (Vivado)  (interfaces, packages, modports)
#
# Prerequisites:
#   source ~/future_prep/scripts/activate_qprep.sh

WAVES_DIR := ../waves
BUILD_DIR := build
RTL_DIR   := rtl
TB_DIR    := tb

.PHONY: all ex01 ex02 ex03 ex04 ex05 ex06 ex07 axi_stream clean check_dirs

# ─── Top-level ────────────────────────────────────────────────────────────────
all: check_dirs ex01 ex02 ex03 ex04 ex05 ex06 ex07 axi_stream
	@echo ""
	@echo "============================================"
	@echo " M01 ALL EXERCISES COMPLETE"
	@echo " VCDs in $(WAVES_DIR)/m01_*.vcd"
	@echo "============================================"

check_dirs:
	@mkdir -p $(BUILD_DIR) $(WAVES_DIR)

# ─── iverilog helper ─────────────────────────────────────────────────────────
# Usage: $(call IVERILOG_RUN, exercise_name, rtl_files, tb_file)
define IVERILOG_RUN
	@echo "--- [iverilog] $1 ---"
	iverilog -g2012 -Wall \
	  -o $(BUILD_DIR)/$1.vvp \
	  $2 $3
	vvp $(BUILD_DIR)/$1.vvp
	@echo ""
endef

# ─── xsim helper ─────────────────────────────────────────────────────────────
# Usage: $(call XSIM_RUN, exercise_name, snap_name, rtl_files, tb_file)
define XSIM_RUN
	@echo "--- [xsim] $1 ---"
	@mkdir -p $(BUILD_DIR)/xsim_$1
	cd $(BUILD_DIR)/xsim_$1 && \
	  xvlog --sv $(addprefix ../../,$3) $(addprefix ../../,$4) 2>&1 | grep -vE "^$$|^Vivado" ; \
	  xelab $2 -s $2_snap 2>&1 | grep -E "ERROR|Built|WARNING" ; \
	  xsim $2_snap --runall 2>&1 | grep -E "PASS|FAIL|ALL|ERROR|Info:|finish"
	@echo ""
endef

# ─── Ex01: D flip-flop (iverilog) ────────────────────────────────────────────
ex01: check_dirs
	$(call IVERILOG_RUN,ex01,$(RTL_DIR)/ex01_dff.sv,$(TB_DIR)/tb_ex01_dff.sv)

# ─── Ex02: Shift register (iverilog) ─────────────────────────────────────────
ex02: check_dirs
	$(call IVERILOG_RUN,ex02,$(RTL_DIR)/ex02_shift_reg.sv,$(TB_DIR)/tb_ex02_shift_reg.sv)

# ─── Ex03: typedef/enum/struct (iverilog) ────────────────────────────────────
ex03: check_dirs
	$(call IVERILOG_RUN,ex03,$(RTL_DIR)/ex03_typedef_enum.sv,$(TB_DIR)/tb_ex03_typedef_enum.sv)

# ─── Ex04: FSM (iverilog) ────────────────────────────────────────────────────
ex04: check_dirs
	$(call IVERILOG_RUN,ex04,$(RTL_DIR)/ex04_fsm.sv,$(TB_DIR)/tb_ex04_fsm.sv)

# ─── Ex05: Interface + modport (xsim) ────────────────────────────────────────
ex05: check_dirs
	$(call XSIM_RUN,ex05,tb_ex05_interface,\
	  $(RTL_DIR)/ex05_interface.sv,\
	  $(TB_DIR)/tb_ex05_interface.sv)

# ─── Ex06: Package (xsim) ────────────────────────────────────────────────────
ex06: check_dirs
	$(call XSIM_RUN,ex06,tb_ex06_pkg,\
	  $(RTL_DIR)/ex06_pkg.sv $(RTL_DIR)/ex06_top.sv,\
	  $(TB_DIR)/tb_ex06_pkg.sv)

# ─── Ex07: Synchronous FIFO (xsim) ───────────────────────────────────────────
ex07: check_dirs
	$(call XSIM_RUN,ex07,tb_ex07_sync_fifo,\
	  $(RTL_DIR)/ex07_sync_fifo.sv,\
	  $(TB_DIR)/tb_ex07_sync_fifo.sv)

# ─── Day 3: AXI4-Stream FIFO + SVA (xsim — concurrent assertions need xsim) ───
# Compiles the DUT, the bound SVA checker, and the self-checking TB together.
# The `bind` in sva_fifo_props.sv injects the checker into the FIFO instance,
# so the assertions run automatically during the directed + randomized tests.
axi_stream: check_dirs
	$(call XSIM_RUN,axi_stream,tb_axi_stream_fifo,\
	  $(RTL_DIR)/axi_stream_fifo.sv $(RTL_DIR)/sva_fifo_props.sv,\
	  $(TB_DIR)/tb_axi_stream_fifo.sv)

# ─── Clean ───────────────────────────────────────────────────────────────────
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(WAVES_DIR)/m01_*.vcd
	@echo "Cleaned."
