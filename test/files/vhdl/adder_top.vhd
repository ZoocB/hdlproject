library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity adder_top is
    generic (
        G_DATA_WIDTH : integer := 4
    );
    port (
        clk     : in  std_logic;
        rst     : in  std_logic;
        sw_a    : in  std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        sw_b    : in  std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        btn_add : in  std_logic;
        led_sum : out std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        led_cry : out std_logic;
        led_cnt : out std_logic_vector(3 downto 0)
    );
end entity adder_top;

architecture rtl of adder_top is

    signal sum_result : std_logic_vector(G_DATA_WIDTH - 1 downto 0);
    signal carry_out  : std_logic;
    signal count      : std_logic_vector(3 downto 0);

    component counter is
        port (
            clk   : in  std_logic;
            rst   : in  std_logic;
            en    : in  std_logic;
            count : out std_logic_vector(3 downto 0)
        );
    end component counter;

begin

    u_adder : entity work.adder_core
        generic map (
            G_DATA_WIDTH => G_DATA_WIDTH
        )
        port map (
            a     => sw_a,
            b     => sw_b,
            sum   => sum_result,
            carry => carry_out
        );

    u_status : entity work.status_reg
        generic map (
            G_DATA_WIDTH => G_DATA_WIDTH
        )
        port map (
            clk => clk,
            rst => rst,
            en  => btn_add,
            d   => sum_result,
            q   => led_sum
        );

    u_counter : counter
        port map (
            clk   => clk,
            rst   => rst,
            en    => btn_add,
            count => count
        );

    led_cry <= carry_out;
    led_cnt <= count;

end architecture rtl;
