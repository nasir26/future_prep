// =============================================================================
// M09 — axis_pkg: compiles the environment as one UVM class library
// =============================================================================
//
// Deliberately no `timescale directive: this package is `include`d
// alongside Xilinx's own uvm_pkg (linked in via `-L uvm`, precompiled
// without one), and xsim's cross-design timescale check treats a
// package-level `timescale as needing to match literally everything
// linked in — including libraries we don't control. Every module and
// interface we author (tb_top.sv, axis_if.sv, the DUT) still declares
// `timescale 1ns/1ps; the package itself just stays silent on it.
// `include (not separate xvlog compilation units) because UVM class
// declarations must all be visible to each other's forward references
// (e.g. axis_env.sv referencing axis_agent, axis_scoreboard) — packaging
// them together is the standard UVM project layout, and it's also why the
// files are ordered leaves-first (item -> sequencer/driver/monitor ->
// agent -> scoreboard/env -> sequences/tests).
//
package axis_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"

    `include "axis_seq_item.sv"
    `include "axis_sequencer.sv"
    `include "axis_driver.sv"
    `include "axis_monitor.sv"
    `include "axis_agent.sv"
    `include "axis_scoreboard.sv"
    `include "axis_env.sv"
    `include "axis_sequences.sv"
    `include "axis_tests.sv"
endpackage
