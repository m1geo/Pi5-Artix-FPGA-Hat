`timescale 1ns / 1ps
//
// George Smart, M1GEO
// Pi5-Artix50T-Hat Blinky LED Example Verilog
// March 2024
// https://github.com/m1geo/Pi5-Artix-FPGA-Hat
//

module top(
    input clk50m,
    output led
    );
    
    reg [23:0] counter;
    assign led = counter[23]; // (50 MHz)/(2^(23+1)) = 2.9 Hz
    
    // Run the counter at 50 MHz
    always @ (posedge clk50m) begin
        counter <= counter + 1'b1;
    end
    
endmodule
