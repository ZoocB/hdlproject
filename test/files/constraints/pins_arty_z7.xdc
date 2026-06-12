## Arty Z7-20 Pin Assignments
## Reference: Arty Z7 Schematic and Master XDC

## Clock - 125 MHz from Zynq PS (directly via FCLK_CLK0, directly useable in PL)
## Using an external clock input on pin H16 for standalone PL testing
set_property -dict {PACKAGE_PIN H16 IOSTANDARD LVCMOS33} [get_ports clk]

## Reset - Active high, directly mapped to BTN0
set_property -dict {PACKAGE_PIN D19 IOSTANDARD LVCMOS33} [get_ports rst]

## Button - BTN1 used as add trigger
set_property -dict {PACKAGE_PIN D20 IOSTANDARD LVCMOS33} [get_ports btn_add]

## Switches - directly mapped to sw_a and sw_b inputs
## sw_a[3:0] mapped to Pmod Header JA (accent top row)
set_property -dict {PACKAGE_PIN Y18 IOSTANDARD LVCMOS33} [get_ports {sw_a[0]}]
set_property -dict {PACKAGE_PIN Y19 IOSTANDARD LVCMOS33} [get_ports {sw_a[1]}]
set_property -dict {PACKAGE_PIN Y16 IOSTANDARD LVCMOS33} [get_ports {sw_a[2]}]
set_property -dict {PACKAGE_PIN Y17 IOSTANDARD LVCMOS33} [get_ports {sw_a[3]}]

## sw_b[3:0] mapped to Pmod Header JA (accent bottom row)
set_property -dict {PACKAGE_PIN U18 IOSTANDARD LVCMOS33} [get_ports {sw_b[0]}]
set_property -dict {PACKAGE_PIN U19 IOSTANDARD LVCMOS33} [get_ports {sw_b[1]}]
set_property -dict {PACKAGE_PIN W18 IOSTANDARD LVCMOS33} [get_ports {sw_b[2]}]
set_property -dict {PACKAGE_PIN W19 IOSTANDARD LVCMOS33} [get_ports {sw_b[3]}]

## LEDs - directly mapped to LED outputs
## led_sum[3:0] mapped to LEDs LD0-LD3
set_property -dict {PACKAGE_PIN R14 IOSTANDARD LVCMOS33} [get_ports {led_sum[0]}]
set_property -dict {PACKAGE_PIN P14 IOSTANDARD LVCMOS33} [get_ports {led_sum[1]}]
set_property -dict {PACKAGE_PIN N16 IOSTANDARD LVCMOS33} [get_ports {led_sum[2]}]
set_property -dict {PACKAGE_PIN M14 IOSTANDARD LVCMOS33} [get_ports {led_sum[3]}]

## Carry LED - mapped to RGB LED 0 (green channel)
set_property -dict {PACKAGE_PIN G17 IOSTANDARD LVCMOS33} [get_ports led_cry]

## Counter LEDs - mapped to Pmod Header JB (top row)
set_property -dict {PACKAGE_PIN T14 IOSTANDARD LVCMOS33} [get_ports {led_cnt[0]}]
set_property -dict {PACKAGE_PIN U14 IOSTANDARD LVCMOS33} [get_ports {led_cnt[1]}]
set_property -dict {PACKAGE_PIN U15 IOSTANDARD LVCMOS33} [get_ports {led_cnt[2]}]
set_property -dict {PACKAGE_PIN V17 IOSTANDARD LVCMOS33} [get_ports {led_cnt[3]}]
