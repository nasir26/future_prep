// =============================================================================
// M09 ex01 — axis_driver: turns sequence items into pin wiggles
// =============================================================================
//
// WHY ONE DRIVER CLASS DRIVES TWO DIFFERENT PROTOCOLS' WORTH OF SIGNALS
//   A "producer" driver puts tvalid/tdata/tlast on the bus and waits for
//   tready (drives the DUT's slave port). A "consumer" driver puts tready
//   on the bus and waits for tvalid (drives the DUT's master port). These
//   are genuinely different pieces of code — but they're not a genuinely
//   different *component*: same UVM phases, same get_next_item/item_done
//   protocol, same virtual-interface plumbing. `axis_dir_e mode` (set via
//   uvm_config_db from the agent, see axis_agent.sv) picks which drive_*()
//   task runs; that's the entire difference. This mirrors the AxisSource
//   vs. AxisSink split in M02's cocotb BFM (fifo_bfm.py) — same protocol
//   knowledge, expressed here as UVM config instead of two Python classes.
//
typedef enum { DRIVE_PRODUCER, DRIVE_CONSUMER } axis_dir_e;

class axis_driver extends uvm_driver #(axis_seq_item);
    `uvm_component_utils(axis_driver)

    virtual axis_if  vif;
    axis_dir_e       mode;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual axis_if)::get(this, "", "vif", vif))
            `uvm_fatal("NOVIF", "axis_driver: no virtual interface set for this component")
        if (!uvm_config_db#(axis_dir_e)::get(this, "", "mode", mode))
            `uvm_fatal("NOMODE", "axis_driver: no axis_dir_e mode set for this component")
    endfunction

    task run_phase(uvm_phase phase);
        // Bus reset: both drive roles start deasserted and wait out reset
        // here rather than in the sequence — a sequence shouldn't need to
        // know the DUT's reset polarity or duration.
        vif.tvalid = 0;
        vif.tdata  = '0;
        vif.tlast  = 0;
        vif.tready = 0;
        @(negedge vif.rst);

        if (mode == DRIVE_PRODUCER) drive_producer();
        else                        drive_consumer();
    endtask

    // ── Producer role: drives s_axis_* (slave port) ─────────────────────────
    // AXI-Stream source obligation: once tvalid is asserted, tdata/tlast
    // must hold stable until tready is seen — so we assert-then-wait, never
    // re-randomize mid-beat.
    task drive_producer();
        forever begin
            seq_item_port.get_next_item(req);
            vif.tvalid = 1;
            vif.tdata  = req.data;
            vif.tlast  = req.last;
            do @(posedge vif.clk); while (!vif.tready);
            vif.tvalid = 0;
            seq_item_port.item_done();
        end
    endtask

    // ── Consumer role: drives m_axis_tready (master port) ───────────────────
    // Each item is "one backpressure interval, then accept one beat" —
    // req.ready_delay cycles of tready=0, then tready=1 until a transfer
    // actually completes (tvalid may still be 0 if the FIFO is empty).
    task drive_consumer();
        forever begin
            seq_item_port.get_next_item(req);
            repeat (req.ready_delay) begin
                vif.tready = 0;
                @(posedge vif.clk);
            end
            vif.tready = 1;
            do @(posedge vif.clk); while (!(vif.tvalid && vif.tready));
            seq_item_port.item_done();
        end
    endtask
endclass
