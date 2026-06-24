"""
fifo_bfm.py — M02 Bus Functional Model (BFM) classes
=====================================================
Shared protocol layer for AXI4-Stream FIFO tests.
Import these into any test file instead of redefining them per-file.

Classes
-------
AxisSource   — drives the slave (write) port of the FIFO
AxisSink     — drives the master (read) port and collects beats
Scoreboard   — compares observed outputs to expected (reference model)

Design pattern notes
--------------------
Driver   = pushes legal stimulus to DUT inputs following the protocol timing.
Monitor  = passively observes an interface and delivers transactions upward.
Scoreboard = compares observed transactions to the expected golden sequence.

Timing note
-----------
Handshake signals (s_axis_tready, m_axis_tvalid, m_axis_tdata, m_axis_tlast)
are COMBINATIONAL in axis_fifo.sv — they are based on registers (fill_level,
rd_ptr) from the PREVIOUS clock edge.  cocotb's VPI callback fires at the
rising-edge timestep BEFORE iverilog's always @(posedge clk) blocks execute,
so reading these signals immediately after RisingEdge gives the correct
handshake value.  Using Timer(1ps) here would advance past the delta cycles
and see the POST-edge register values, causing the handshake check to fail
when the FIFO fills (tready drops) or empties (tvalid drops) on the last beat.

Rule: use RisingEdge (no Timer) for handshake signal sampling in BFM.
      use RisingEdge + Timer(1ps) in test code to read registered outputs.

Author: Nasir Ali, C-DAC Noida
"""

from cocotb.triggers import RisingEdge


# ═══════════════════════════════════════════════════════════════════════════
#  AxisSource — AXI4-Stream slave-port driver
# ═══════════════════════════════════════════════════════════════════════════

class AxisSource:
    """
    Drives s_axis_t{valid,data,last} following the AXI4-Stream handshake.

    Handshake rule (spec §2.2.1):
      A transfer completes on the rising edge where BOTH tvalid AND tready are 1.
      Once tvalid is asserted, the source MUST NOT deassert it until the
      handshake completes.

    This driver deasserts tvalid between beats (non-burst mode) for clarity.
    """

    def __init__(self, dut):
        self._dut = dut
        dut.s_axis_tvalid.value = 0
        dut.s_axis_tdata.value  = 0
        dut.s_axis_tlast.value  = 0

    async def send(self, data: int, last: bool = False) -> None:
        """Present one beat and block until the slave accepts it (tready=1)."""
        self._dut.s_axis_tvalid.value = 1
        self._dut.s_axis_tdata.value  = data
        self._dut.s_axis_tlast.value  = int(last)
        while True:
            await RisingEdge(self._dut.clk)
            # s_axis_tready = ~full is combinational based on fill_level from
            # the PREVIOUS cycle.  Read it here (pre-RTL-execute) for the
            # correct handshake check.  Adding Timer(1ps) would see the
            # POST-edge fill_level and incorrectly report tready=0 on the
            # beat that fills the FIFO, causing an infinite loop.
            if int(self._dut.s_axis_tready.value) == 1:
                break
        self._dut.s_axis_tvalid.value = 0

    async def send_packet(self, payload: list) -> None:
        """Send a list of ints as one AXI-Stream packet (tlast on the last beat)."""
        for idx, byte in enumerate(payload):
            is_last = (idx == len(payload) - 1)
            await self.send(byte, last=is_last)


# ═══════════════════════════════════════════════════════════════════════════
#  AxisSink — AXI4-Stream master-port driver + beat collector
# ═══════════════════════════════════════════════════════════════════════════

class AxisSink:
    """
    Controls m_axis_tready and collects accepted (data, tlast) beats.

    Parameters
    ----------
    always_ready : bool
        If True, tready is permanently 1 (no back-pressure).
        Set to False to control tready manually for back-pressure scenarios.
    """

    def __init__(self, dut, always_ready: bool = True):
        self._dut = dut
        self._dut.m_axis_tready.value = int(always_ready)

    async def recv_beat(self) -> tuple:
        """Block until one beat is accepted; return (data: int, tlast: int)."""
        while True:
            await RisingEdge(self._dut.clk)
            # m_axis_tvalid = ~empty and m_axis_tdata/tlast = mem[rd_ptr] are
            # all combinational from pre-edge registers.  Read them here
            # (before RTL executes) so the last-beat handshake is not missed
            # (at +1ps, fill_level has decremented to 0, tvalid becomes 0).
            if (int(self._dut.m_axis_tvalid.value) == 1 and
                    int(self._dut.m_axis_tready.value) == 1):
                return (int(self._dut.m_axis_tdata.value),
                        int(self._dut.m_axis_tlast.value))

    async def recv_packet(self) -> list:
        """Collect beats until tlast=1; return list of (data, tlast) tuples."""
        packet = []
        while True:
            beat = await self.recv_beat()
            packet.append(beat)
            if beat[1]:
                break
        return packet


# ═══════════════════════════════════════════════════════════════════════════
#  Scoreboard — expected vs. observed checker
# ═══════════════════════════════════════════════════════════════════════════

class Scoreboard:
    """
    Reference model for the AXI4-Stream FIFO.

    Usage
    -----
    1. sb.expect(data, last)  before each beat you send.
    2. sb.check(data, last)   after each beat is observed.
    3. sb.assert_done()       at the end to verify all expected beats arrived.
    """

    def __init__(self, log):
        from collections import deque
        self._expected = deque()
        self._errors   = 0
        self._log      = log

    def expect(self, data: int, last: bool = False) -> None:
        self._expected.append((int(data), int(last)))

    def check(self, data: int, last: int) -> None:
        if not self._expected:
            self._errors += 1
            self._log.error(
                f"Unexpected beat: data=0x{data:02X} last={last} (queue empty)"
            )
            return
        exp_data, exp_last = self._expected.popleft()
        if data != exp_data or last != exp_last:
            self._errors += 1
            self._log.error(
                f"MISMATCH — got: 0x{data:02X}/{last} | expected: 0x{exp_data:02X}/{exp_last}"
            )

    def assert_done(self) -> None:
        remaining = len(self._expected)
        assert self._errors   == 0, f"{self._errors} scoreboard mismatch(es)"
        assert remaining      == 0, (
            f"{remaining} expected beat(s) never received: "
            + ", ".join(f"(0x{d:02X},{l})" for d, l in self._expected)
        )
