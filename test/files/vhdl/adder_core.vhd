library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity adder_core is
    generic (
        G_DATA_WIDTH : integer := 8
    );
    port (
        a      : in  std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        b      : in  std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        sum    : out std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        carry  : out std_logic
    );
end entity adder_core;

architecture rtl of adder_core is
    signal sum_ext : unsigned(G_DATA_WIDTH downto 0);
begin

    sum_ext <= resize(unsigned(a), G_DATA_WIDTH + 1)
             + resize(unsigned(b), G_DATA_WIDTH + 1);

    sum   <= std_logic_vector(sum_ext(G_DATA_WIDTH - 1 downto 0));
    carry <= sum_ext(G_DATA_WIDTH);

end architecture rtl;
