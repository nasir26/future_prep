#!/usr/bin/env bash
# Source this file to get both Vivado AND the qprep conda env in one step:
#   source ~/future_prep/scripts/activate_qprep.sh

# Init conda for this shell session
CONDA_BASE=~/miniforge3
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate qprep

# Bring in Vivado/xsim
source "$(dirname "${BASH_SOURCE[0]}")/setup_vivado.sh"

echo ""
echo "=== qprep environment ready ==="
echo "  Python : $(python --version)"
echo "  iverilog: $(iverilog -V 2>&1 | head -1)"
echo "  verilator: $(verilator --version 2>&1 | head -1)"
echo "  xsim  : $(xsim --version 2>&1 | head -1)"
echo ""
echo "Waveform dumps land in ~/future_prep/waves/"
echo "Open *.vcd files with the Surfer extension in VS Code."
