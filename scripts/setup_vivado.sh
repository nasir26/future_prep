#!/usr/bin/env bash
# Source this file (do NOT run it) to put Vivado 2023.2 on PATH:
#   source ~/future_prep/scripts/setup_vivado.sh
#
# Also sets XILINX_VIVADO so downstream tools (xelab, etc.) find their libs.

VIVADO_ROOT=/tools/Xilinx/Vivado/2023.2

if [[ ! -d "$VIVADO_ROOT" ]]; then
    echo "ERROR: Vivado not found at $VIVADO_ROOT" >&2
    return 1
fi

export XILINX_VIVADO="$VIVADO_ROOT"
export PATH="$VIVADO_ROOT/bin:$PATH"

# Vitis HLS/common library path (needed by xelab for IP sim models)
VITIS_ROOT=/tools/Xilinx/Vitis/2023.2
if [[ -d "$VITIS_ROOT/bin" ]]; then
    export PATH="$VITIS_ROOT/bin:$PATH"
fi

echo "Vivado 2023.2 on PATH: $(which xsim)"
xsim --version 2>/dev/null | head -1
