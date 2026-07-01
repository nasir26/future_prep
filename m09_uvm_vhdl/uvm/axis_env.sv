// =============================================================================
// M09 ex03 — axis_env: wires two agents + one scoreboard together
// =============================================================================
//
// This is deliberately the thinnest file in the environment: build two
// agents (their own build_phase does the mode/vif config_db work), build
// one scoreboard, connect each agent's monitor analysis port to the right
// scoreboard export. All the "what does producer vs. consumer even mean"
// logic lives in axis_agent.sv/axis_driver.sv — the env just names the two
// instances and wires analysis ports, which is exactly the level of
// abstraction a UVM env is supposed to sit at.
//
class axis_env extends uvm_env;
    `uvm_component_utils(axis_env)

    axis_agent       producer_agent;   // drives s_axis_* (into the FIFO)
    axis_agent       consumer_agent;   // drives m_axis_tready (out of the FIFO)
    axis_scoreboard  sb;

    virtual axis_if  prod_vif;
    virtual axis_if  cons_vif;

    function new(string name, uvm_component parent);
        super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);

        if (!uvm_config_db#(virtual axis_if)::get(this, "", "prod_vif", prod_vif))
            `uvm_fatal("NOVIF", "axis_env: no prod_vif set")
        if (!uvm_config_db#(virtual axis_if)::get(this, "", "cons_vif", cons_vif))
            `uvm_fatal("NOVIF", "axis_env: no cons_vif set")

        uvm_config_db#(axis_dir_e)::set(this, "producer_agent", "mode", DRIVE_PRODUCER);
        uvm_config_db#(virtual axis_if)::set(this, "producer_agent", "vif", prod_vif);
        uvm_config_db#(axis_dir_e)::set(this, "consumer_agent", "mode", DRIVE_CONSUMER);
        uvm_config_db#(virtual axis_if)::set(this, "consumer_agent", "vif", cons_vif);

        producer_agent = axis_agent::type_id::create("producer_agent", this);
        producer_agent.is_active = UVM_ACTIVE;

        consumer_agent = axis_agent::type_id::create("consumer_agent", this);
        consumer_agent.is_active = UVM_ACTIVE;

        sb = axis_scoreboard::type_id::create("sb", this);
    endfunction

    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        producer_agent.mon.ap.connect(sb.expected_export);
        consumer_agent.mon.ap.connect(sb.actual_export);
    endfunction
endclass
