"""
axil_bfm.py — AXI4-Lite Master BFM
====================================
Minimal write + read transactions for cocotb testbenches.

AXI4-Lite protocol recap
------------------------
Write: drive AWVALID+AWADDR and WVALID+WDATA simultaneously.
       Wait for both AWREADY and WREADY (can arrive in any order).
       Then wait for BVALID, assert BREADY.

Read:  drive ARVALID+ARADDR.
       Wait for ARREADY.
       Wait for RVALID, assert RREADY, capture RDATA.

Timing: all handshake signals sampled at RisingEdge (pre-RTL-execute).
        Same rule as fifo_bfm.py — combinational ready signals must be
        read before the RTL executes the clock edge.

Author: Nasir Ali, C-DAC Noida
"""

from cocotb.triggers import RisingEdge, Timer

_SETTLE = Timer(1, unit="ps")


class AxilMaster:
    """Drive AXI4-Lite write and read transactions."""

    def __init__(self, dut, clk, prefix="s_axil_"):
        self._dut = dut
        self._clk = clk
        self._p   = prefix
        self._idle()

    def _idle(self):
        """Deassert all initiator signals."""
        d = self._dut
        p = self._p
        getattr(d, f"{p}awvalid").value = 0
        getattr(d, f"{p}awaddr").value  = 0
        getattr(d, f"{p}wvalid").value  = 0
        getattr(d, f"{p}wdata").value   = 0
        getattr(d, f"{p}wstrb").value   = 0xF
        getattr(d, f"{p}bready").value  = 0
        getattr(d, f"{p}arvalid").value = 0
        getattr(d, f"{p}araddr").value  = 0
        getattr(d, f"{p}rready").value  = 0

    async def write(self, addr: int, data: int) -> None:
        """Perform one AXI4-Lite write transaction."""
        d, p = self._dut, self._p

        # Drive address and data channels simultaneously
        getattr(d, f"{p}awaddr").value  = addr
        getattr(d, f"{p}awvalid").value = 1
        getattr(d, f"{p}wdata").value   = data & 0xFFFF_FFFF
        getattr(d, f"{p}wstrb").value   = 0xF
        getattr(d, f"{p}wvalid").value  = 1

        aw_done = False
        w_done  = False
        while not (aw_done and w_done):
            await RisingEdge(self._clk)
            # Sample ready signals at posedge (pre-RTL) — combinational outputs
            if not aw_done and int(getattr(d, f"{p}awready").value) == 1:
                getattr(d, f"{p}awvalid").value = 0
                aw_done = True
            if not w_done and int(getattr(d, f"{p}wready").value) == 1:
                getattr(d, f"{p}wvalid").value = 0
                w_done = True

        # Wait for write response
        getattr(d, f"{p}bready").value = 1
        while True:
            await RisingEdge(self._clk)
            if int(getattr(d, f"{p}bvalid").value) == 1:
                break
        getattr(d, f"{p}bready").value = 0

    async def read(self, addr: int) -> int:
        """Perform one AXI4-Lite read transaction; return RDATA."""
        d, p = self._dut, self._p

        getattr(d, f"{p}araddr").value  = addr
        getattr(d, f"{p}arvalid").value = 1

        while True:
            await RisingEdge(self._clk)
            if int(getattr(d, f"{p}arready").value) == 1:
                break
        getattr(d, f"{p}arvalid").value = 0

        getattr(d, f"{p}rready").value = 1
        while True:
            await RisingEdge(self._clk)
            if int(getattr(d, f"{p}rvalid").value) == 1:
                rdata = int(getattr(d, f"{p}rdata").value)
                break
        getattr(d, f"{p}rready").value = 0

        return rdata
