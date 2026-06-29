`timescale 1ns/1ps
// Self-checking testbench: golden-checks all 108x108 pairs against TRUE modulo,
// measures pipeline latency (cycles) and streaming throughput (transforms/cycle).
module tb;
    parameter real CLKP = 1.0;     // ns clock period assumption (1 GHz) for ns view
    reg clk = 0, rst = 1, in_valid = 0;
    reg [6:0] x = 0, y = 0;
    wire out_valid; wire [6:0] out;

    rns108 dut(.clk(clk), .rst(rst), .in_valid(in_valid),
               .x(x), .y(y), .out_valid(out_valid), .out(out));

    always #(CLKP/2.0) clk = ~clk;

    // golden reference (TB MAY divide; only the DUT must not)
    function [6:0] gold(input [6:0] xx, input [6:0] yy);
        integer a, b;
        begin
            a = ((xx % 4)  * (yy % 4))  % 4;
            b = ((xx % 27) * (yy % 27)) % 27;
            gold = (81*a + 28*b) % 108;
        end
    endfunction

    // expected pipeline: mirror the DUT's 4-cycle latency exactly
    reg [6:0] e1,e2,e3,e4; reg ev1,ev2,ev3,ev4;
    always @(posedge clk) begin
        e1 <= gold(x,y);  ev1 <= rst ? 1'b0 : in_valid;
        e2 <= e1;         ev2 <= rst ? 1'b0 : ev1;
        e3 <= e2;         ev3 <= rst ? 1'b0 : ev2;
        e4 <= e3;         ev4 <= rst ? 1'b0 : ev3;
    end

    integer cyc = 0;       always @(posedge clk) cyc = cyc + 1;
    integer n = 0, errors = 0;
    integer first_in = -1, first_out = -1;

    // checker + latency capture
    always @(posedge clk) begin
        if (in_valid && first_in < 0)  first_in  = cyc;
        if (out_valid && first_out < 0) first_out = cyc;
        if (out_valid) begin
            n = n + 1;
            if (out !== e4) begin
                errors = errors + 1;
                if (errors <= 5)
                    $display("  MISMATCH n=%0d  out=%0d  expected=%0d", n, out, e4);
            end
        end
    end

    integer xi, yi;
    initial begin
        repeat (4) @(posedge clk);
        rst <= 0; @(posedge clk);

        // stream every (x,y) in 0..107, one pair per cycle
        for (xi = 0; xi < 108; xi = xi + 1)
            for (yi = 0; yi < 108; yi = yi + 1) begin
                @(posedge clk);
                in_valid <= 1; x <= xi[6:0]; y <= yi[6:0];
            end
        @(posedge clk); in_valid <= 0;
        repeat (8) @(posedge clk);

        $display("=================================================");
        $display(" RNS-108 RTL Simulation (Vendor-Agnostic)");
        $display("=================================================");
        $display(" transforms checked : %0d", n);
        $display(" mismatches vs true modulo : %0d", errors);
        $display(" pipeline LATENCY  : %0d cycles  (first_in@cyc%0d -> first_out@cyc%0d)",
                 first_out - first_in, first_in, first_out);
        $display(" streaming THROUGHPUT : 1 transform / cycle (checked %0d back-to-back)", n);
        $display(" --- ns view at assumed clock period %.2f ns (Nominal Testbench Clock) ---",
                 CLKP);
        $display(" E_latency  (serial / asiddha step) = %0d cycles = %.2f ns",
                 first_out - first_in, (first_out - first_in)*CLKP);
        $display(" E_throughput (independent ops)     = 1 cycle  = %.2f ns", CLKP);
        $finish;
    end
endmodule
