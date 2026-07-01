// =============================================================================
// Day 4: AXI4-Lite slave register file — 4 read/write 32-bit registers
// =============================================================================
`timescale 1ns/1ps
//
// CONCEPT: why AXI4-Lite has FIVE independent channels
//   Full AXI4 pipelines bursts; AXI4-Lite strips that down to single-beat
//   register access, but still keeps write address (AW), write data (W),
//   write response (B), read address (AR) and read data (R) as five
//   separate valid/ready handshakes. AW and W are deliberately independent
//   — a legal master may assert AWVALID and WVALID on different cycles,
//   in either order — so this slave must be able to latch whichever one
//   shows up first and wait for its partner. That's the one subtlety that
//   makes AXI-Lite slaves harder to get right than they look.
//
// REGISTER MAP (word-aligned, ADDR_W=4 -> exactly 4 words, no illegal
// addresses to decode-error on — keeps this exercise's response coding to
// OKAY-only, which is the honest scope for "4 registers"):
//   0x0  REG0 — bit 0 doubles as `gate_en_o`, the enable gate_fifo_sv.sv
//               reads (see tb_axi_lite_regfile.sv for the wiring). Bits
//               [31:1] are plain storage, same as the other three.
//   0x4  REG1 — plain R/W scratch register
//   0x8  REG2 — plain R/W scratch register
//   0xC  REG3 — plain R/W scratch register
//
module axi_lite_regfile #(
    parameter int ADDR_W = 4     // 16 bytes = 4 word-aligned registers
) (
    input  logic                  clk,
    input  logic                  rst,          // active-high, synchronous

    // ── Write address channel ────────────────────────────────────────────────
    input  logic [ADDR_W-1:0]     s_axil_awaddr,
    input  logic                  s_axil_awvalid,
    output logic                  s_axil_awready,

    // ── Write data channel ───────────────────────────────────────────────────
    input  logic [31:0]           s_axil_wdata,
    input  logic [3:0]            s_axil_wstrb,
    input  logic                  s_axil_wvalid,
    output logic                  s_axil_wready,

    // ── Write response channel ───────────────────────────────────────────────
    output logic [1:0]            s_axil_bresp,
    output logic                  s_axil_bvalid,
    input  logic                  s_axil_bready,

    // ── Read address channel ─────────────────────────────────────────────────
    input  logic [ADDR_W-1:0]     s_axil_araddr,
    input  logic                  s_axil_arvalid,
    output logic                  s_axil_arready,

    // ── Read data channel ────────────────────────────────────────────────────
    output logic [31:0]           s_axil_rdata,
    output logic [1:0]            s_axil_rresp,
    output logic                  s_axil_rvalid,
    input  logic                  s_axil_rready,

    // ── Side-band: reg0[0] exposed directly, no AXI read needed to see it ────
    output logic                  gate_en_o
);

    localparam logic [1:0] RESP_OKAY = 2'b00;

    logic [31:0] regs [0:3];

    assign gate_en_o = regs[0][0];

    // ── Write channel: independent AW/W latch-and-wait ──────────────────────
    typedef enum { W_IDLE, W_WAIT_DATA, W_WAIT_ADDR, W_RESP } wr_state_t;
    wr_state_t          wr_state;
    logic [ADDR_W-1:0]  awaddr_latched;

    always_ff @(posedge clk) begin
        if (rst) begin
            wr_state       <= W_IDLE;
            s_axil_awready <= 1'b0;
            s_axil_wready  <= 1'b0;
            s_axil_bvalid  <= 1'b0;
            s_axil_bresp   <= RESP_OKAY;
            regs[0]        <= '0;
            regs[1]        <= '0;
            regs[2]        <= '0;
            regs[3]        <= '0;
        end else begin
            // Defaults: readies pulse for exactly the cycle they're needed.
            s_axil_awready <= 1'b0;
            s_axil_wready  <= 1'b0;

            case (wr_state)
                // Accept whichever of AW/W arrives first; both ready lines
                // are high here so a master presenting both at once (the
                // common case) completes in one cycle.
                W_IDLE: begin
                    s_axil_awready <= 1'b1;
                    s_axil_wready  <= 1'b1;
                    if (s_axil_awvalid && s_axil_wvalid) begin
                        write_regs(s_axil_awaddr, s_axil_wdata, s_axil_wstrb);
                        s_axil_bvalid <= 1'b1;
                        wr_state      <= W_RESP;
                    end else if (s_axil_awvalid) begin
                        awaddr_latched <= s_axil_awaddr;
                        wr_state       <= W_WAIT_DATA;
                    end else if (s_axil_wvalid) begin
                        // WVALID arrived alone: hold the data channel open
                        // (wready stays low; we re-assert it once AW lands)
                        // and wait for AWVALID instead.
                        wr_state <= W_WAIT_ADDR;
                    end
                end

                W_WAIT_DATA: begin
                    s_axil_wready <= 1'b1;
                    if (s_axil_wvalid) begin
                        write_regs(awaddr_latched, s_axil_wdata, s_axil_wstrb);
                        s_axil_bvalid <= 1'b1;
                        wr_state      <= W_RESP;
                    end
                end

                W_WAIT_ADDR: begin
                    s_axil_awready <= 1'b1;
                    if (s_axil_awvalid) begin
                        // s_axil_wdata/wstrb are still valid — WVALID hasn't
                        // been deasserted because we never asserted wready.
                        write_regs(s_axil_awaddr, s_axil_wdata, s_axil_wstrb);
                        s_axil_bvalid <= 1'b1;
                        wr_state      <= W_RESP;
                    end
                end

                W_RESP: begin
                    if (s_axil_bready) begin
                        s_axil_bvalid <= 1'b0;
                        wr_state      <= W_IDLE;
                    end
                end
            endcase
        end
    end

    // Per-byte-lane write, gated by WSTRB — the AXI-Lite way to support
    // sub-word writes without a separate byte-enable protocol.
    task automatic write_regs(input logic [ADDR_W-1:0] addr,
                               input logic [31:0]       data,
                               input logic [3:0]        strb);
        int idx;
        idx = int'(addr[3:2]);
        for (int b = 0; b < 4; b++)
            if (strb[b]) regs[idx][8*b +: 8] <= data[8*b +: 8];
    endtask

    // ── Read channel: latch address, present data one cycle later ───────────
    typedef enum { R_IDLE, R_DATA } rd_state_t;
    rd_state_t rd_state;

    always_ff @(posedge clk) begin
        if (rst) begin
            rd_state       <= R_IDLE;
            s_axil_arready <= 1'b0;
            s_axil_rvalid  <= 1'b0;
            s_axil_rresp   <= RESP_OKAY;
            s_axil_rdata   <= '0;
        end else begin
            s_axil_arready <= 1'b0;

            case (rd_state)
                R_IDLE: begin
                    s_axil_arready <= 1'b1;
                    if (s_axil_arvalid) begin
                        s_axil_rdata  <= regs[int'(s_axil_araddr[3:2])];
                        s_axil_rvalid <= 1'b1;
                        rd_state      <= R_DATA;
                    end
                end

                R_DATA: begin
                    if (s_axil_rready) begin
                        s_axil_rvalid <= 1'b0;
                        rd_state      <= R_IDLE;
                    end
                end
            endcase
        end
    end

    // ── SVA: the handshake rules AXI4-Lite requires of every channel ─────────
    // Inline (not a bound checker like Day 3's sva_fifo_props.sv) because
    // this module is authored fresh here, not an existing DUT being verified
    // non-intrusively — see gate_fifo_sv.sv / sva_gate_fifo_props.sv for the
    // "port existing RTL, verify from outside" case Day 3 established.
    default clocking cb @(posedge clk); endclocking

    // VALID must not be withdrawn before its READY is seen (all 5 channels).
    ap_awvalid_held: assert property (disable iff (rst)
        (s_axil_awvalid && !s_axil_awready) |=> s_axil_awvalid)
        else $error("[SVA] s_axil_awvalid dropped before awready");

    ap_wvalid_held: assert property (disable iff (rst)
        (s_axil_wvalid && !s_axil_wready) |=> s_axil_wvalid)
        else $error("[SVA] s_axil_wvalid dropped before wready");

    ap_arvalid_held: assert property (disable iff (rst)
        (s_axil_arvalid && !s_axil_arready) |=> s_axil_arvalid)
        else $error("[SVA] s_axil_arvalid dropped before arready");

    // Slave-driven VALIDs (B, R) must hold until their READY is seen too.
    ap_bvalid_held: assert property (disable iff (rst)
        (s_axil_bvalid && !s_axil_bready) |=> s_axil_bvalid)
        else $error("[SVA] s_axil_bvalid dropped before bready");

    ap_rvalid_held: assert property (disable iff (rst)
        (s_axil_rvalid && !s_axil_rready) |=> s_axil_rvalid)
        else $error("[SVA] s_axil_rvalid dropped before rready");

    // FSM/output consistency: each response channel's VALID must line up
    // exactly with its own FSM being in the state that's supposed to drive
    // it — this is what would break if a future edit reordered a state or
    // forgot to gate an assignment.
    ap_bvalid_matches_state: assert property (disable iff (rst)
        s_axil_bvalid |-> (wr_state == W_RESP))
        else $error("[SVA] bvalid high outside W_RESP");

    ap_rvalid_matches_state: assert property (disable iff (rst)
        s_axil_rvalid |-> (rd_state == R_DATA))
        else $error("[SVA] rvalid high outside R_DATA");

endmodule
