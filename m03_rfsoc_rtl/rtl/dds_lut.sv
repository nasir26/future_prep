// dds_lut.sv — Direct Digital Synthesizer: Phase Accumulator + LUT
// =================================================================
// M03 ex01: The heart of every RFSoC signal chain.
//
// Architecture
// ------------
//   PINC register → 32-bit phase accumulator (wraps mod 2^32)
//   Top LUT_BITS of accumulator → address into 1024-entry sine ROM
//   ROM output → pipelined dds_sine / dds_cos (1-cycle latency)
//
// Frequency resolution: Fclk / 2^PHASE_W
//   At 100 MHz, PHASE_W=32 → ~0.023 Hz per LSB of PINC
// Frequency tuning:   PINC = round(Fo / Fclk * 2^PHASE_W)
//   Fo=10 MHz, Fclk=100 MHz → PINC = 429_496_730
//
// AXI4-Lite register map (4-byte word-addressed)
//   0x00 CTRL  [0]=enable  [1]=sync_rst
//   0x04 PINC  phase increment (frequency word)
//   0x08 POFF  phase offset  (top LUT_BITS used)
//
// Sine LUT
//   Loaded from file via $readmemh at simulation start.
//   Path passed via +lut_file=<path> plusarg (default: dds_sine_lut.hex).
//   1024 entries × 16-bit signed two's-complement (range ±32767).
//
// Latency: 1 clock cycle (LUT output registered)
// Author: Nasir Ali, C-DAC Noida

`timescale 1ns/1ps
module dds_lut #(
    parameter LUT_BITS = 10,    // LUT addr width → 2^LUT_BITS = 1024 entries
    parameter DATA_W   = 16,    // output width (signed)
    parameter PHASE_W  = 32,    // phase accumulator width
    parameter AXI_AW   = 4     // AXI4-Lite addr width (covers 3 × 4-byte regs)
)(
    input  wire                  clk,
    input  wire                  rst_n,

    // ── AXI4-Lite slave ─────────────────────────────────────────────────
    input  wire [AXI_AW-1:0]    s_axil_awaddr,
    input  wire                  s_axil_awvalid,
    output wire                  s_axil_awready,
    input  wire [31:0]           s_axil_wdata,
    input  wire [3:0]            s_axil_wstrb,
    input  wire                  s_axil_wvalid,
    output wire                  s_axil_wready,
    output wire [1:0]            s_axil_bresp,
    output wire                  s_axil_bvalid,
    input  wire                  s_axil_bready,
    input  wire [AXI_AW-1:0]    s_axil_araddr,
    input  wire                  s_axil_arvalid,
    output wire                  s_axil_arready,
    output wire [31:0]           s_axil_rdata,
    output wire [1:0]            s_axil_rresp,
    output wire                  s_axil_rvalid,
    input  wire                  s_axil_rready,

    // ── DDS output ──────────────────────────────────────────────────────
    output reg signed [DATA_W-1:0]  dds_sine,
    output reg signed [DATA_W-1:0]  dds_cos,
    output reg                       dds_valid
);

    // ═══════════════════════════════════════════════════════════════════
    //  Control registers
    // ═══════════════════════════════════════════════════════════════════
    reg [31:0] reg_ctrl;    // [0]=enable [1]=sync_rst
    reg [31:0] reg_pinc;    // phase increment
    reg [31:0] reg_poff;    // phase offset

    wire dds_en   = reg_ctrl[0];
    wire sync_rst = reg_ctrl[1];

    // ═══════════════════════════════════════════════════════════════════
    //  AXI4-Lite write path
    //  Simple one-at-a-time latch: hold AW and W independently,
    //  write register when both are latched, then send B response.
    // ═══════════════════════════════════════════════════════════════════
    reg                  aw_pend;
    reg [AXI_AW-1:0]    aw_addr;
    reg                  w_pend;
    reg [31:0]           w_data;

    assign s_axil_awready = ~aw_pend;
    assign s_axil_wready  = ~w_pend;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_pend <= 0; aw_addr <= '0;
            w_pend  <= 0; w_data  <= '0;
            reg_ctrl <= '0; reg_pinc <= '0; reg_poff <= '0;
        end else begin
            if (s_axil_awvalid && s_axil_awready) begin
                aw_pend <= 1; aw_addr <= s_axil_awaddr;
            end
            if (s_axil_wvalid && s_axil_wready) begin
                w_pend  <= 1; w_data  <= s_axil_wdata;
            end
            if (aw_pend && w_pend) begin
                aw_pend <= 0; w_pend <= 0;
                case (aw_addr[3:2])
                    2'd0: reg_ctrl <= w_data;
                    2'd1: reg_pinc <= w_data;
                    2'd2: reg_poff <= w_data;
                    default: ;
                endcase
            end
        end
    end

    // B-channel: assert bvalid one cycle after register write, hold until bready
    reg bvalid_r;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)                     bvalid_r <= 0;
        else if (aw_pend && w_pend)     bvalid_r <= 1;
        else if (s_axil_bready)         bvalid_r <= 0;
    end
    assign s_axil_bvalid = bvalid_r;
    assign s_axil_bresp  = 2'b00;  // OKAY

    // ═══════════════════════════════════════════════════════════════════
    //  AXI4-Lite read path
    // ═══════════════════════════════════════════════════════════════════
    reg        rvalid_r;
    reg [31:0] rdata_r;

    assign s_axil_arready = ~rvalid_r;
    assign s_axil_rvalid  = rvalid_r;
    assign s_axil_rdata   = rdata_r;
    assign s_axil_rresp   = 2'b00;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rvalid_r <= 0; rdata_r <= '0;
        end else if (s_axil_arvalid && s_axil_arready) begin
            rvalid_r <= 1;
            case (s_axil_araddr[3:2])
                2'd0: rdata_r <= reg_ctrl;
                2'd1: rdata_r <= reg_pinc;
                2'd2: rdata_r <= reg_poff;
                default: rdata_r <= '0;
            endcase
        end else if (s_axil_rready) begin
            rvalid_r <= 0;
        end
    end

    // ═══════════════════════════════════════════════════════════════════
    //  Phase accumulator
    //  32-bit natural overflow = exact modulo-2^32 phase wrap.
    // ═══════════════════════════════════════════════════════════════════
    reg [PHASE_W-1:0] phase_acc;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n || sync_rst) phase_acc <= '0;
        else if (dds_en)        phase_acc <= phase_acc + reg_pinc;
    end

    // ═══════════════════════════════════════════════════════════════════
    //  Sine LUT (ROM)
    //  Top LUT_BITS of phase_acc select the table entry.
    //  Cosine is 90° ahead = quarter-period offset = 2^(LUT_BITS-2) entries.
    //  POFF shifts the entire output phase (top LUT_BITS used).
    // ═══════════════════════════════════════════════════════════════════
    localparam LUT_DEPTH = 1 << LUT_BITS;

    reg signed [DATA_W-1:0] lut [0:LUT_DEPTH-1];

    // Path supplied via plusarg; fallback for manual vvp runs
    initial begin : lut_init
        string lut_file;
        if (!$value$plusargs("lut_file=%s", lut_file))
            lut_file = "dds_sine_lut.hex";
        $readmemh(lut_file, lut);
    end

    wire [LUT_BITS-1:0] sin_addr =
        phase_acc[PHASE_W-1 -: LUT_BITS] + reg_poff[PHASE_W-1 -: LUT_BITS];
    wire [LUT_BITS-1:0] cos_addr =
        sin_addr + (LUT_DEPTH >> 2);   // +quarter period = +π/2

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            dds_sine  <= '0;
            dds_cos   <= '0;
            dds_valid <= 0;
        end else if (dds_en) begin
            // Only latch LUT values when enabled; holds zero (or last value)
            // when disabled so the reset test sees zero outputs.
            dds_sine  <= lut[sin_addr];
            dds_cos   <= lut[cos_addr];
            dds_valid <= 1;
        end else begin
            dds_valid <= 0;
        end
    end

endmodule
