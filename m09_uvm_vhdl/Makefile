# Makefile — Module 09: UVM + VHDL
#
# Invoke from m09_uvm_vhdl/:
#   cd ~/future_prep/m09_uvm_vhdl && make all
#
# Targets:
#   make all    — uvm/ (smoke + random UVM tests) + vhdl/ (mixed-language UART)
#   make clean  — clean both subdirectories
#
# Prerequisites:
#   source ~/future_prep/scripts/activate_qprep.sh

.PHONY: all uvm vhdl clean

all: uvm vhdl
	@echo ""
	@echo "============================================"
	@echo " M09 ALL TARGETS COMPLETE"
	@echo "============================================"

uvm:
	$(MAKE) -C uvm all

vhdl:
	$(MAKE) -C vhdl all

clean:
	$(MAKE) -C uvm clean
	$(MAKE) -C vhdl clean
