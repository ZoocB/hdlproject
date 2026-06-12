library ieee;
use ieee.std_logic_1164.all;

entity status_reg is
    generic (
        G_DATA_WIDTH : integer := 8
    );
    port (
        clk    : in  std_logic;
        rst    : in  std_logic;
        en     : in  std_logic;
        d      : in  std_logic_vector(G_DATA_WIDTH - 1 downto 0);
        q      : out std_logic_vector(G_DATA_WIDTH - 1 downto 0)
    );
end entity status_reg;

architecture rtl of status_reg is
begin

    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                q <= (others => '0');
            elsif en = '1' then
                q <= d;
            end if;
        end if;
    end process;

end architecture rtl;
