## Timing Constraints for Arty Z7-20 Test Project

## Primary clock - 125 MHz (8 ns period)
create_clock -period 8.000 -name sys_clk -waveform {0.000 4.000} [get_ports clk]

## Input delay constraints
set_input_delay -clock sys_clk -max 2.0 [get_ports {sw_a[*]}]
set_input_delay -clock sys_clk -min 0.5 [get_ports {sw_a[*]}]
set_input_delay -clock sys_clk -max 2.0 [get_ports {sw_b[*]}]
set_input_delay -clock sys_clk -min 0.5 [get_ports {sw_b[*]}]
set_input_delay -clock sys_clk -max 2.0 [get_ports btn_add]
set_input_delay -clock sys_clk -min 0.5 [get_ports btn_add]
set_input_delay -clock sys_clk -max 2.0 [get_ports rst]
set_input_delay -clock sys_clk -min 0.5 [get_ports rst]

## Output delay constraints
set_output_delay -clock sys_clk -max 2.0 [get_ports {led_sum[*]}]
set_output_delay -clock sys_clk -min 0.5 [get_ports {led_sum[*]}]
set_output_delay -clock sys_clk -max 2.0 [get_ports led_cry]
set_output_delay -clock sys_clk -min 0.5 [get_ports led_cry]
set_output_delay -clock sys_clk -max 2.0 [get_ports {led_cnt[*]}]
set_output_delay -clock sys_clk -min 0.5 [get_ports {led_cnt[*]}]
