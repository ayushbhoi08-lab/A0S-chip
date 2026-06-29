`timescale 1ns/1ps
module tb;
    localparam integer Q = 12289;
    localparam integer NTEST = 3000000;
    reg clk=0, rst=1, in_valid=0;
    reg [13:0] x, y;
    wire out_valid; wire [13:0] out;
    ntt_mul12289 dut(.clk(clk),.rst(rst),.in_valid(in_valid),.x(x),.y(y),
                     .out_valid(out_valid),.out(out));
    always #0.5 clk=~clk;
    reg [27:0] cx=0, cy=0;
    function [13:0] gold(input [27:0] xx, input [27:0] yy); gold=(xx*yy)%Q; endfunction
    reg [13:0] e1,e2,e3,e4; reg ev1,ev2,ev3,ev4;
    always @(posedge clk) begin
        e1<=gold(cx,cy); ev1<=rst?1'b0:in_valid;
        e2<=e1; ev2<=rst?1'b0:ev1; e3<=e2; ev3<=rst?1'b0:ev2; e4<=e3; ev4<=rst?1'b0:ev3;
    end
    integer cyc=0; always @(posedge clk) cyc=cyc+1;
    integer n=0, errors=0, first_in=-1, first_out=-1;
    always @(posedge clk) begin
        if (in_valid && first_in<0) first_in=cyc;
        if (out_valid && first_out<0) first_out=cyc;
        if (out_valid) begin n=n+1;
            if (out!==e4) begin errors=errors+1;
                if (errors<=5) $display("  MISMATCH n=%0d out=%0d exp=%0d", n, out, e4); end
        end
    end
    task drive(input [13:0] xi, input [13:0] yi);
        begin @(posedge clk); in_valid<=1; cx<=xi; cy<=yi; x<=xi; y<=yi; end
    endtask
    integer i; reg [31:0] rx, ry;
    initial begin
        repeat(4) @(posedge clk); rst<=0; @(posedge clk);
        drive(0,0); drive(1,1); drive(Q-1,Q-1); drive(Q-1,2); drive(12288,12288);
        drive(6144,2); drive(0,Q-1); drive(7,11);
        for (i=0;i<NTEST;i=i+1) begin rx=$random; ry=$random; drive(rx%Q, ry%Q); end
        @(posedge clk); in_valid<=0; repeat(8) @(posedge clk);
        $display("=== ntt_mul12289  [(x*y) mod 12289] ===");
        $display(" checked=%0d  mismatches=%0d  latency=%0d cyc", n, errors, first_out-first_in);
        $finish;
    end
endmodule
