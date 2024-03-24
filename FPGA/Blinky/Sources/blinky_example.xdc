#
# George Smart, M1GEO
# Pi5-Artix50T-Hat Blinky LED Example Constraints
# March 2024
# https://github.com/m1geo/Pi5-Artix-FPGA-Hat
#

# Clock (50MHz) on J19
set_property -dict { PACKAGE_PIN J19 IOSTANDARD LVCMOS33 } [get_ports { clk50m }];
create_clock -period 20.00 [get_ports { clk50m }];

# LED on AB1
set_property -dict { PACKAGE_PIN AB1 IOSTANDARD LVCMOS33 } [get_ports { led }];
