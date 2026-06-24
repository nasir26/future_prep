// timed_sequencer.sv — Mini tProc (Timed Processor)
// ====================================================
// M03 ex03: Stripped-down version of QICK's timed processor.
//
// Instruction set (5 opcodes, fixed 64-bit encoding)
// ---------------------------------------------------
//  Bits [63:60] = OPCODE
//
//  WAIT   (0x0): halt execution for DELAY cycles
//    [59:28] = DELAY (32-bit, in clock cycles); 0 = fall-through
//
//  SET_FREQ (0x1): write PINC to DDS phase increment output port
//    [59:28] = PINC value
//
//  FIRE   (0x2): assert pulse_trigger for one cycle
//    [59:28] = DURATION (pulse length hint forwarded to pulse engine)
//
//  READ_CTR (0x3): capture photon_count into result register
//    (no operand)
//
//  BRANCH (0x4): jump if result_reg < THRESHOLD
//    [59:28] = THRESHOLD  [27:16] = TARGET_ADDR
//
//  HALT   (0xF): stop execution, set DONE
//    (any opcode > 4 also halts — unused slots default to 0xF)
//
// Program memory
//   64-bit instructions, depth = 2^PROG_BITS (default 32).
//   Unused slots initialised to HALT (0xF000…) so PC falling off
//   the end of written code automatically stops the sequencer.
//
// AXI4-Lite register map
//   0x00  CTRL       [0]=RUN  [1]=DONE(RO)
//   0x04  PC         current program counter (RO during run)
//   0x08  RESULT     last READ_CTR result (RO)
//   0x0C  PROG_WR    write pointer (set before loading program)
//   0x10  PROG_LO    instruction low  32 bits (write first)
//   0x14  PROG_HI    instruction high 32 bits (write second; commits + auto-inc ptr)
//
// Output ports
//   dds_pinc        — updated when SET_FREQ executes
//   pulse_trigger   — 1-cycle strobe when FIRE executes
//   pulse_duration  — operand forwarded from FIRE
//   ctr_capture     — 1-cycle strobe on READ_CTR
//
// Author: Nasir Ali, C-DAC Noida

`timescale 1ns/1ps
module timed_sequencer #(
    parameter PROG_BITS = 5,    // program depth = 2^5 = 32 instructions
    parameter AXI_AW    = 5    // covers 0x00–0x1C
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

    // Sequencer outputs
    output reg [31:0]            dds_pinc,
    output reg                   pulse_trigger,
    output reg [31:0]            pulse_duration,
    output reg                   ctr_capture,
    input  wire [31:0]           photon_count,

    output wire                  seq_running,
    output wire                  seq_done
);

    // ═══════════════════════════════════════════════════════════════════
    //  Opcodes
    // ═══════════════════════════════════════════════════════════════════
    localparam [3:0]
        OP_WAIT     = 4'h0,
        OP_SET_FREQ = 4'h1,
        OP_FIRE     = 4'h2,
        OP_READ_CTR = 4'h3,
        OP_BRANCH   = 4'h4,
        OP_HALT     = 4'hF;

    // ═══════════════════════════════════════════════════════════════════
    //  Control state (separate flops, not packed into one reg_ctrl)
    // ═══════════════════════════════════════════════════════════════════
    reg run_r, done_r;
    assign seq_running = run_r;
    assign seq_done    = done_r;

    // ═══════════════════════════════════════════════════════════════════
    //  Program memory: depth = 2^PROG_BITS × 64 bits
    //  Unused entries initialised to HALT opcode (0xF000…) so PC
    //  falling off the end of user code automatically terminates.
    // ═══════════════════════════════════════════════════════════════════
    localparam PROG_DEPTH = 1 << PROG_BITS;

    reg [63:0] prog_mem [0:PROG_DEPTH-1];

    initial begin : init_prog
        integer i;
        for (i = 0; i < PROG_DEPTH; i = i + 1)
            prog_mem[i] = 64'hF000_0000_0000_0000;  // HALT
    end

    // Program write path (AXI-driven, separate from execute)
    reg [PROG_BITS-1:0] prog_wr_ptr;
    reg                  prog_lo_pend;
    reg [31:0]           prog_lo_buf;

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
            run_r        <= 0;
            done_r       <= 0;
            prog_wr_ptr  <= '0;
            prog_lo_pend <= 0;
            prog_lo_buf  <= '0;
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
                    3'd0: begin   // CTRL
                        if (w_data[0]) begin
                            run_r  <= 1;
                            done_r <= 0;
                        end
                    end
                    3'd3: prog_wr_ptr <= w_data[PROG_BITS-1:0];  // set write pointer
                    3'd4: begin   // PROG_LO — buffer low word
                        prog_lo_buf  <= w_data;
                        prog_lo_pend <= 1;
                    end
                    3'd5: begin   // PROG_HI — commit instruction
                        if (prog_lo_pend) begin
                            prog_mem[prog_wr_ptr] <= {w_data, prog_lo_buf};
                            prog_wr_ptr           <= prog_wr_ptr + 1;
                            prog_lo_pend          <= 0;
                        end
                    end
                    default: ;
                endcase
            end
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

    reg [PROG_BITS-1:0] pc_exposed;   // snapshot for AXI read
    reg [31:0]          result_r;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin rvalid_r <= 0; rdata_r <= '0; end
        else if (s_axil_arvalid && s_axil_arready) begin
            rvalid_r <= 1;
            case (s_axil_araddr[4:2])
                3'd0: rdata_r <= {30'h0, done_r, run_r};
                3'd1: rdata_r <= {27'h0, pc_exposed};
                3'd2: rdata_r <= result_r;
                3'd3: rdata_r <= {27'h0, prog_wr_ptr};
                default: rdata_r <= '0;
            endcase
        end else if (s_axil_rready) rvalid_r <= 0;
    end

    // ═══════════════════════════════════════════════════════════════════
    //  Sequencer FSM
    // ═══════════════════════════════════════════════════════════════════
    typedef enum logic [1:0] {
        S_IDLE  = 2'b00,
        S_FETCH = 2'b01,
        S_EXEC  = 2'b10,
        S_WAIT  = 2'b11
    } state_t;

    state_t             state;
    reg [PROG_BITS-1:0] pc;
    reg [63:0]          instr;
    reg [31:0]          wait_cnt;

    wire [3:0]  opcode   = instr[63:60];
    wire [31:0] operand  = instr[59:28];
    wire [11:0] tgt_addr = instr[27:16];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state          <= S_IDLE;
            pc             <= '0;
            pc_exposed     <= '0;
            instr          <= 64'hF000_0000_0000_0000;
            wait_cnt       <= '0;
            result_r       <= '0;
            dds_pinc       <= '0;
            pulse_trigger  <= 0;
            pulse_duration <= '0;
            ctr_capture    <= 0;
        end else begin
            // Default: deassert strobes every cycle
            pulse_trigger <= 0;
            ctr_capture   <= 0;

            case (state)
                S_IDLE: begin
                    if (run_r) begin
                        pc    <= '0;
                        state <= S_FETCH;
                    end
                end

                S_FETCH: begin
                    instr      <= prog_mem[pc];
                    pc_exposed <= pc;
                    state      <= S_EXEC;
                end

                S_EXEC: begin
                    case (opcode)
                        OP_WAIT: begin
                            if (operand == 0) begin
                                pc    <= pc + 1;
                                state <= S_FETCH;
                            end else begin
                                wait_cnt <= operand - 1;
                                state    <= S_WAIT;
                            end
                        end
                        OP_SET_FREQ: begin
                            dds_pinc <= operand;
                            pc       <= pc + 1;
                            state    <= S_FETCH;
                        end
                        OP_FIRE: begin
                            pulse_trigger  <= 1;
                            pulse_duration <= operand;
                            pc             <= pc + 1;
                            state          <= S_FETCH;
                        end
                        OP_READ_CTR: begin
                            ctr_capture <= 1;
                            result_r    <= photon_count;
                            pc          <= pc + 1;
                            state       <= S_FETCH;
                        end
                        OP_BRANCH: begin
                            pc    <= (result_r < operand)
                                     ? tgt_addr[PROG_BITS-1:0]
                                     : pc + 1;
                            state <= S_FETCH;
                        end
                        default: begin   // OP_HALT (0xF) or any unknown → stop
                            run_r  <= 0;
                            done_r <= 1;
                            state  <= S_IDLE;
                        end
                    endcase
                end

                S_WAIT: begin
                    if (wait_cnt == 0) begin
                        pc    <= pc + 1;
                        state <= S_FETCH;
                    end else begin
                        wait_cnt <= wait_cnt - 1;
                    end
                end
            endcase
        end
    end

endmodule
