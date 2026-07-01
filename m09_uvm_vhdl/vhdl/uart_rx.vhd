-------------------------------------------------------------------------------
-- M09 — uart_rx: minimal UART receiver, mirrors uart_tx's 8-N-1 framing.
-------------------------------------------------------------------------------
--
-- CONCEPT: sample at bit CENTER, not bit EDGE
--   The receiver has no clock from the transmitter — it only has the
--   serial line and its own local clock. If it sampled right at the start
--   of each bit period, any clock-rate mismatch or start-bit-detection
--   jitter would risk sampling the transition itself instead of a settled
--   value. Waiting CLKS_PER_BIT/2 cycles after the start-bit edge, then
--   CLKS_PER_BIT cycles between each subsequent sample, means every sample
--   lands mid-bit — maximally far from either neighboring transition. This
--   is the one idea that makes async serial reception work at all.
--
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity uart_rx is
    generic (
        CLKS_PER_BIT : integer := 4    -- must match the paired uart_tx
    );
    port (
        clk         : in  std_logic;
        rst         : in  std_logic;    -- active-high, synchronous

        i_rx_serial : in  std_logic;
        o_rx_dv     : out std_logic;    -- 1-cycle pulse: o_rx_byte is valid
        o_rx_byte   : out std_logic_vector(7 downto 0)
    );
end entity uart_rx;

architecture rtl of uart_rx is

    type state_t is (IDLE, START_BIT, DATA_BITS, STOP_BIT);
    signal state    : state_t := IDLE;

    signal clk_count : integer range 0 to CLKS_PER_BIT - 1 := 0;
    signal bit_index : integer range 0 to 7 := 0;
    signal rx_byte   : std_logic_vector(7 downto 0) := (others => '0');

begin

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state     <= IDLE;
                clk_count <= 0;
                bit_index <= 0;
                o_rx_dv   <= '0';
                o_rx_byte <= (others => '0');
            else
                o_rx_dv <= '0';   -- default: strobe deasserts every cycle

                case state is

                    when IDLE =>
                        clk_count <= 0;
                        bit_index <= 0;
                        if i_rx_serial = '0' then   -- falling edge = start bit
                            state <= START_BIT;
                        end if;

                    when START_BIT =>
                        -- Walk to the CENTER of the start bit, then confirm
                        -- it's still low — a real UART would treat "still
                        -- high here" as a glitch and abort back to IDLE;
                        -- this minimal version assumes a clean line (the
                        -- mixed-language TB drives one directly, no noise
                        -- model needed for what this exercise is teaching).
                        if clk_count < (CLKS_PER_BIT - 1) / 2 then
                            clk_count <= clk_count + 1;
                        else
                            clk_count <= 0;
                            state     <= DATA_BITS;
                        end if;

                    when DATA_BITS =>
                        if clk_count < CLKS_PER_BIT - 1 then
                            clk_count <= clk_count + 1;
                        else
                            clk_count          <= 0;
                            rx_byte(bit_index) <= i_rx_serial;   -- LSB first
                            if bit_index < 7 then
                                bit_index <= bit_index + 1;
                            else
                                bit_index <= 0;
                                state     <= STOP_BIT;
                            end if;
                        end if;

                    when STOP_BIT =>
                        if clk_count < CLKS_PER_BIT - 1 then
                            clk_count <= clk_count + 1;
                        else
                            clk_count <= 0;
                            o_rx_byte <= rx_byte;
                            o_rx_dv   <= '1';
                            state     <= IDLE;
                        end if;

                end case;
            end if;
        end if;
    end process;

end architecture rtl;
