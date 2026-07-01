-------------------------------------------------------------------------------
-- M09 — uart_tx: minimal UART transmitter (8-N-1: 8 data bits, no parity,
-- 1 stop bit), one bit per CLKS_PER_BIT clock cycles.
-------------------------------------------------------------------------------
--
-- WHY CLKS_PER_BIT IS A GENERIC, NOT A CONSTANT
--   A real UART divides the system clock down to the baud rate (e.g.
--   50 MHz / 115200 baud = 434 clocks/bit). Simulating 434 clocks per bit
--   x 10 bits x however many bytes makes for a slow, waveform-unreadable
--   testbench. Exposing CLKS_PER_BIT as a generic means the mixed-language
--   testbench (tb_uart_mixed.sv) can instantiate this with a tiny value
--   (4) for fast, inspectable simulation, while a real FPGA build would
--   set it from actual clock/baud math — same RTL, different generic.
--
-- CONCEPT: the FSM is the entire protocol
--   IDLE: line held high (UART idle state is logic 1).
--   START: drive the line low for one bit period — this is what an RX
--          state machine watches for to know a byte is coming.
--   DATA:  8 bits, LSB first (the UART convention), one per bit period.
--   STOP:  drive the line high for one bit period, then back to IDLE.
--
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity uart_tx is
    generic (
        CLKS_PER_BIT : integer := 4    -- sim default; real builds set this
                                        -- from clk_freq_hz / baud_rate
    );
    port (
        clk        : in  std_logic;
        rst        : in  std_logic;    -- active-high, synchronous

        i_data     : in  std_logic_vector(7 downto 0);
        i_dv       : in  std_logic;    -- 1-cycle pulse: "transmit i_data now"
        o_tx_active : out std_logic;   -- high for the whole byte transmission
        o_tx_serial : out std_logic;   -- the actual UART line
        o_tx_done   : out std_logic    -- 1-cycle pulse when the stop bit completes
    );
end entity uart_tx;

architecture rtl of uart_tx is

    type state_t is (IDLE, START_BIT, DATA_BITS, STOP_BIT);
    signal state       : state_t := IDLE;

    signal clk_count    : integer range 0 to CLKS_PER_BIT - 1 := 0;
    signal bit_index    : integer range 0 to 7 := 0;
    signal data_latched : std_logic_vector(7 downto 0) := (others => '0');

begin

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state        <= IDLE;
                clk_count    <= 0;
                bit_index    <= 0;
                o_tx_active  <= '0';
                o_tx_serial  <= '1';   -- idle line is high
                o_tx_done    <= '0';
            else
                o_tx_done <= '0';   -- default: strobe deasserts every cycle

                case state is

                    when IDLE =>
                        o_tx_serial <= '1';
                        o_tx_active <= '0';
                        clk_count   <= 0;
                        bit_index   <= 0;
                        if i_dv = '1' then
                            data_latched <= i_data;   -- capture — i_data may
                                                        -- change the very next
                                                        -- cycle, ours must not
                            o_tx_active  <= '1';
                            state        <= START_BIT;
                        end if;

                    when START_BIT =>
                        o_tx_serial <= '0';
                        if clk_count < CLKS_PER_BIT - 1 then
                            clk_count <= clk_count + 1;
                        else
                            clk_count <= 0;
                            state     <= DATA_BITS;
                        end if;

                    when DATA_BITS =>
                        -- LSB first — the UART wire convention.
                        o_tx_serial <= data_latched(bit_index);
                        if clk_count < CLKS_PER_BIT - 1 then
                            clk_count <= clk_count + 1;
                        else
                            clk_count <= 0;
                            if bit_index < 7 then
                                bit_index <= bit_index + 1;
                            else
                                bit_index <= 0;
                                state     <= STOP_BIT;
                            end if;
                        end if;

                    when STOP_BIT =>
                        o_tx_serial <= '1';
                        if clk_count < CLKS_PER_BIT - 1 then
                            clk_count <= clk_count + 1;
                        else
                            clk_count   <= 0;
                            o_tx_active <= '0';
                            o_tx_done   <= '1';
                            state       <= IDLE;
                        end if;

                end case;
            end if;
        end if;
    end process;

end architecture rtl;
