// photon_counter.sv — Simulated PMT Photon Counter
// ==================================================
// M03 ex04: Models single-photon counting with Poisson noise.
//
// In a real ion-trap experiment, a PMT (photo-multiplier tube) detects
// fluorescence photons.  The detection count follows a Poisson distribution:
//   bright state: mean ≈ N_bright (high count)
//   dark  state:  mean ≈ N_dark   (near zero)
// A threshold discriminates the two states.
//
// This RTL module provides:
//   1. A programmable MEAN register (expected photon count per window).
//   2. A 32-bit Galois LFSR for pseudo-random number generation.
//   3. On each capture_trigger pulse: COUNT = clip(MEAN + noise, 0, 255)
//      where noise is a bounded random perturbation drawn from the LFSR.
//   4. A THRESHOLD register: BRIGHT if COUNT > THRESH, DARK otherwise.
//   5. An AXI4-Lite interface for all control/status registers.
//
// AXI4-Lite register map (4-byte aligned)
//   0x00  CTRL        [0]=SOFT_CAPTURE (software-triggered capture)
//   0x04  MEAN        expected photon count (0–255)
//   0x08  NOISE_AMP   ±noise bound (0–127, default 8)
//   0x0C  THRESHOLD   state discrimination threshold
//   0x10  COUNT       last captured count (read-only)
//   0x14  STATE       0=DARK, 1=BRIGHT (read-only, COUNT > THRESHOLD)
//
// Input ports
//   capture_trigger  — 1-cycle strobe from sequencer READ_CTR instruction
//
// Output ports
//   photon_count  — current COUNT value (wired to sequencer photon_count port)
//
// LFSR note
//   32-bit Galois LFSR, polynomial x^32+x^22+x^2+x+1 (period 2^32-1).
//   Seeded to 0xDEAD_BEEF at reset.  CTRL[1] reseeds from NOISE_AMP[31:0].
//
// Author: Nasir Ali, C-DAC Noida

`timescale 1ns/1ps
module photon_counter #(
    parameter AXI_AW = 5   // covers 0x00–0x1C
)(
    input  wire                  clk,
    input  wire                  rst_n,

    // AXI4-Lite slave
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

    // Experiment interface
    input  wire                  capture_trigger,   // from sequencer ctr_capture
    output wire [31:0]           photon_count       // to sequencer photon_count
);

    // ═══════════════════════════════════════════════════════════════════
    //  Control registers
    // ═══════════════════════════════════════════════════════════════════
    reg [31:0] reg_ctrl;
    reg [31:0] reg_mean;
    reg [31:0] reg_noise_amp;
    reg [31:0] reg_threshold;
    reg [31:0] reg_count;
    reg [31:0] reg_state;

    assign photon_count = reg_count;

    // ═══════════════════════════════════════════════════════════════════
    //  16-bit Fibonacci LFSR
    //  Polynomial: x^16 + x^15 + x^13 + x^4 + 1  (maximal, period 65535)
    //  Feedback bit: lfsr[15] ^ lfsr[14] ^ lfsr[12] ^ lfsr[3]
    // ═══════════════════════════════════════════════════════════════════
    reg [15:0] lfsr;
    wire       fb = lfsr[15] ^ lfsr[14] ^ lfsr[12] ^ lfsr[3];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= 16'hACE1;             // non-zero seed
        else if (reg_ctrl[1])             // soft reseed
            lfsr <= reg_noise_amp[15:0] ^ 16'hA5A5;
        else
            lfsr <= {lfsr[14:0], fb};     // shift-left, new LSB = feedback
    end

    // ═══════════════════════════════════════════════════════════════════
    //  Photon count generation
    //  count = clip(MEAN + signed_noise, 0, 255)
    //  noise drawn from lfsr[7:0] mapped to [-NOISE_AMP/2, +NOISE_AMP/2]
    //  (lfsr[7:0] - 128) gives ±128; scale by NOISE_AMP/256 via multiply+shift
    // ═══════════════════════════════════════════════════════════════════
    wire signed [8:0]  noise_raw  = $signed({1'b0, lfsr[7:0]}) - 9'sd128;
    // Scale: noise = noise_raw * NOISE_AMP / 128
    wire signed [17:0] noise_full = noise_raw * $signed({1'b0, reg_noise_amp[6:0]});
    wire signed [8:0]  noise      = noise_full[15:7];  // /128 by right-shift

    wire signed [9:0]  raw_count  = $signed({2'b00, reg_mean[7:0]}) + noise;
    wire [7:0]         clipped    = raw_count[9]  ? 8'h00 :   // underflow → 0
                                    raw_count[8]  ? 8'hFF :   // overflow  → 255
                                    raw_count[7:0];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_count <= '0;
            reg_state <= '0;
        end else if (capture_trigger || reg_ctrl[0]) begin
            reg_count <= {24'h0, clipped};
            reg_state <= (clipped > reg_threshold[7:0]) ? 32'h1 : 32'h0;
        end
    end

    // ═══════════════════════════════════════════════════════════════════
    //  AXI4-Lite write path
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
            reg_ctrl      <= '0;
            reg_mean      <= '0;
            reg_noise_amp <= 32'd8;
            reg_threshold <= 32'd20;
        end else begin
            if (s_axil_awvalid && s_axil_awready) begin
                aw_pend <= 1; aw_addr <= s_axil_awaddr;
            end
            if (s_axil_wvalid && s_axil_wready) begin
                w_pend  <= 1; w_data  <= s_axil_wdata;
            end
            if (aw_pend && w_pend) begin
                aw_pend <= 0; w_pend <= 0;
                case (aw_addr[4:2])
                    3'd0: reg_ctrl      <= w_data;
                    3'd1: reg_mean      <= w_data;
                    3'd2: reg_noise_amp <= w_data;
                    3'd3: reg_threshold <= w_data;
                    default: ;
                endcase
            end
            // Auto-clear SOFT_CAPTURE bit
            if (reg_ctrl[0]) reg_ctrl[0] <= 0;
        end
    end

    reg bvalid_r;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)                 bvalid_r <= 0;
        else if (aw_pend && w_pend) bvalid_r <= 1;
        else if (s_axil_bready)     bvalid_r <= 0;
    end
    assign s_axil_bvalid = bvalid_r;
    assign s_axil_bresp  = 2'b00;

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
        if (!rst_n) begin rvalid_r <= 0; rdata_r <= '0; end
        else if (s_axil_arvalid && s_axil_arready) begin
            rvalid_r <= 1;
            case (s_axil_araddr[4:2])
                3'd0: rdata_r <= reg_ctrl;
                3'd1: rdata_r <= reg_mean;
                3'd2: rdata_r <= reg_noise_amp;
                3'd3: rdata_r <= reg_threshold;
                3'd4: rdata_r <= reg_count;
                3'd5: rdata_r <= reg_state;
                default: rdata_r <= '0;
            endcase
        end else if (s_axil_rready) rvalid_r <= 0;
    end

endmodule
