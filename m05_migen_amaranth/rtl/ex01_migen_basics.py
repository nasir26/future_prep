"""
M05 ex01 — Migen: Signal, comb, sync, If, FSM
===============================================
Migen is the Python HDL used in ARTIQ's gateware (rtio core, phys layer,
DDS core, etc.).  Understanding Migen is essential for reading and extending
ARTIQ source code.

Key concepts
------------
Module      — container for HDL statements; maps to a Verilog module
Signal      — a wire or register value
self.comb   — combinational statements (always @(*))
self.sync   — synchronous statements (always @(posedge sys_clk))
If/Elif/Else — conditional (lowercase function, not keyword)
Case        — switch/case
FSM         — submodules.fsm; finite state machine helper
self.submodules.X — declares a sub-module (instantiated inside)

Contrast with Amaranth (ex02)
------------------------------
The same two designs appear in ex02 using Amaranth 0.5.x syntax so you can
see the differences directly.  Amaranth uses context-manager style control
flow (with m.If(): ...) while Migen uses function-call style (If(...)).

Author: Nasir Ali, C-DAC Noida
"""

from migen import *
from migen.sim import run_simulation


# ═══════════════════════════════════════════════════════════════════════════
#  Design 1 — Parameterized up-counter with synchronous enable/reset
# ═══════════════════════════════════════════════════════════════════════════

class Counter(Module):
    """
    WIDTH-bit synchronous counter.

    Ports
    -----
    en    : input  — count enable (count only when en=1)
    rst   : input  — synchronous reset (resets to 0)
    count : output — current count value
    """

    def __init__(self, width: int = 8):
        # Port declarations (public signals become ports in Verilog)
        self.en    = Signal()
        self.rst   = Signal()
        self.count = Signal(width)

        # ── Synchronous logic ──────────────────────────────────────────
        # self.sync += is shorthand for always @(posedge sys_clk)
        # If() is a Migen expression, NOT a Python if statement.
        # Python if would be evaluated at elaboration time; Migen If()
        # generates HDL conditional logic.
        self.sync += [
            If(self.rst,
                self.count.eq(0),
            ).Elif(self.en,
                self.count.eq(self.count + 1),
            )
        ]


# ═══════════════════════════════════════════════════════════════════════════
#  Design 2 — Two-state FSM: toggle on trigger
# ═══════════════════════════════════════════════════════════════════════════

class ToggleFSM(Module):
    """
    Toggles output every time trigger pulses.
    States: IDLE → ACTIVE → IDLE → ...

    Migen FSM pattern
    -----------------
    self.submodules.fsm creates a named submodule.
    fsm.act("STATE_NAME", statements...) adds a state.
    NextState("NEW_STATE") requests a state transition.
    NextValue(sig, val) is a registered (synchronous) assignment.
    """

    def __init__(self):
        self.trigger = Signal()
        self.out     = Signal()
        self.state   = Signal(2)   # exposed for testbench inspection

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        fsm.act("IDLE",
            # Wait for trigger
            self.state.eq(0),
            If(self.trigger,
                NextValue(self.out, ~self.out),   # toggle
                NextState("WAIT_RELEASE"),
            ),
        )
        fsm.act("WAIT_RELEASE",
            # Hold until trigger deasserts (debounce)
            self.state.eq(1),
            If(~self.trigger,
                NextState("IDLE"),
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Migen testbench helpers
# ═══════════════════════════════════════════════════════════════════════════

def sim_counter(n_cycles: int = 16, width: int = 8) -> list:
    """Run counter simulation; return (rst, en, count) per cycle."""
    dut     = Counter(width)
    log     = []

    def tb():
        # Reset for 2 cycles
        yield dut.rst.eq(1)
        for _ in range(2):
            yield
            log.append((1, 0, (yield dut.count)))
        yield dut.rst.eq(0)

        # Count enabled
        yield dut.en.eq(1)
        for _ in range(n_cycles - 2):
            yield
            log.append((0, 1, (yield dut.count)))

    run_simulation(dut, tb())
    return log


def sim_toggle_fsm() -> list:
    """Run toggle FSM; return (trigger, out, state) per cycle."""
    dut = ToggleFSM()
    log = []

    def tb():
        for trig, n in [(0, 2), (1, 2), (0, 2), (1, 2), (0, 2)]:
            yield dut.trigger.eq(trig)
            for _ in range(n):
                yield
                log.append((
                    (yield dut.trigger),
                    (yield dut.out),
                    (yield dut.state),
                ))

    run_simulation(dut, tb())
    return log


if __name__ == "__main__":
    # Emit VCD for viewing in Surfer
    import os
    waves = os.path.expanduser("~/future_prep/waves")
    dut = Counter()
    def tb():
        yield dut.rst.eq(1); yield; yield
        yield dut.rst.eq(0); yield dut.en.eq(1)
        for _ in range(20): yield

    run_simulation(dut, tb(), vcd_name=f"{waves}/m05_migen_counter.vcd")
    print("VCD written to waves/m05_migen_counter.vcd")
