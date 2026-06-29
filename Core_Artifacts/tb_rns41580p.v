`timescale 1ns/1ps
// Self-checking TB for the DEEP-PIPELINED 5-modulus Ansh-N core (rns41580p).
// Identical stimulus to tb_rns41580.v, but mirrors the 6-cycle latency.
module tb;
    localparam integer M = 41580;
    localparam integer NTEST = 300000;

    reg clk = 0, rst = 1, in_valid = 0;
    reg [1:0] x4, y4;   reg [4:0] x27, y27;  reg [2:0] x5, y5;
    reg [2:0] x7, y7;   reg [3:0] x11, y11;
    wire out_valid;     wire [15:0] out;

    rns41580p dut(.clk(clk), .rst(rst), .in_valid(in_valid),
        .x4(x4), .y4(y4), .x27(x27), .y27(y27), .x5(x5), .y5(y5),
        .x7(x7), .y7(y7), .x11(x11), .y11(y11),
        .out_valid(out_valid), .out(out));

    always #0.5 clk = ~clk;   // 1 ns nominal period

    reg [31:0] cx = 0, cy = 0;
    function [15:0] goldp(input [31:0] xx, input [31:0] yy);
        goldp = (xx * yy) % M;
    endfunction

    // mirror the DUT's exact 6-cycle latency
    reg [15:0] e1,e2,e3,e4,e5,e6; reg ev1,ev2,ev3,ev4,ev5,ev6;
    always @(posedge clk) begin
        e1 <= goldp(cx, cy);  ev1 <= rst ? 1'b0 : in_valid;
        e2 <= e1;             ev2 <= rst ? 1'b0 : ev1;
        e3 <= e2;             ev3 <= rst ? 1'b0 : ev2;
        e4 <= e3;             ev4 <= rst ? 1'b0 : ev3;
        e5 <= e4;             ev5 <= rst ? 1'b0 : ev4;
        e6 <= e5;             ev6 <= rst ? 1'b0 : ev5;
    end

    integer cyc = 0;  always @(posedge clk) cyc = cyc + 1;
    integer n = 0, errors = 0;
    integer first_in = -1, first_out = -1;
    always @(posedge clk) begin
        if (in_valid  && first_in  < 0) first_in  = cyc;
        if (out_valid && first_out < 0) first_out = cyc;
        if (out_valid) begin
            n = n + 1;
            if (out !== e6) begin
                errors = errors + 1;
                if (errors <= 5)
                    $display("  MISMATCH n=%0d  out=%0d expected=%0d", n, out, e6);
            end
        end
    end

    task drive(input [31:0] xi, input [31:0] yi);
        begin
            @(posedge clk);
            in_valid <= 1;
            cx <= xi; cy <= yi;
            x4 <= xi % 4;  x27 <= xi % 27; x5 <= xi % 5; x7 <= xi % 7; x11 <= xi % 11;
            y4 <= yi % 4;  y27 <= yi % 27; y5 <= yi % 5; y7 <= yi % 7; y11 <= yi % 11;
        end
    endtask

    integer i;
    reg [31:0] rx, ry;
    initial begin
        repeat (4) @(posedge clk);
        rst <= 0; @(posedge clk);

        drive(0, 0); drive(1, 1); drive(M-1, M-1); drive(M-1, 2);
        drive(12345, 6789); drive(41579, 41579); drive(0, 41579); drive(27, 11);

        for (i = 0; i < NTEST; i = i + 1) begin
            rx = $random; ry = $random;
            rx = rx % M; ry = ry % M;
            drive(rx, ry);
        end

        @(posedge clk); in_valid <= 0;
        repeat (10) @(posedge clk);

        $display("=================================================");
        $display(" Ansh-N (5-modulus, DEEP-PIPELINED) RTL Sim [Z/41580]");
        $display("=================================================");
        $display(" transforms checked : %0d", n);
        $display(" mismatches vs true (x*y) mod 41580 : %0d", errors);
        $display(" pipeline LATENCY  : %0d cycles  (first_in@cyc%0d -> first_out@cyc%0d)",
                 first_out - first_in, first_in, first_out);
        $display(" streaming THROUGHPUT : 1 transform / cycle (checked %0d back-to-back)", n);
        $finish;
    end
endmodule
