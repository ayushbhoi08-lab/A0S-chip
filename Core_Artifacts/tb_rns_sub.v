`timescale 1ns/1ps
// Self-checking TB for rns_sub: golden-checks (x-y) mod 12289 (least-nonnegative
// residue) over directed corners + >=300k random pairs; measures 2-cycle latency.
// Corners deliberately exercise the borrow path (x<y) where the 14-bit add wraps.
module tb;
    localparam integer Q = 12289;
    localparam integer NTEST = 300000;
    reg clk=0, rst=1, in_valid=0;
    reg [13:0] x, y;
    wire out_valid; wire [13:0] out;
    rns_sub dut(.clk(clk),.rst(rst),.in_valid(in_valid),.x(x),.y(y),
                .out_valid(out_valid),.out(out));
    always #0.5 clk=~clk;

    // golden reference: true least-nonnegative residue of a signed difference
    reg [13:0] cx=0, cy=0;
    function [13:0] gold(input [13:0] xx, input [13:0] yy);
        integer d;
        begin d = xx - yy; if (d<0) d = d + Q; gold = d[13:0]; end
    endfunction

    // mirror the DUT's 2-cycle latency exactly
    reg [13:0] e1,e2; reg ev1,ev2;
    always @(posedge clk) begin
        e1<=gold(cx,cy); ev1<=rst?1'b0:in_valid;
        e2<=e1;          ev2<=rst?1'b0:ev1;
    end

    integer cyc=0; always @(posedge clk) cyc=cyc+1;
    integer n=0, errors=0, first_in=-1, first_out=-1;
    always @(posedge clk) begin
        if (in_valid && first_in<0) first_in=cyc;
        if (out_valid && first_out<0) first_out=cyc;
        if (out_valid) begin n=n+1;
            if (out!==e2) begin errors=errors+1;
                if (errors<=5) $display("  MISMATCH n=%0d x?=%0d y?=%0d out=%0d exp=%0d",
                                        n, cx, cy, out, e2); end
        end
    end

    task drive(input [13:0] xi, input [13:0] yi);
        begin @(posedge clk); in_valid<=1; cx<=xi; cy<=yi; x<=xi; y<=yi; end
    endtask

    integer i; reg [31:0] rx, ry;
    initial begin
        repeat(4) @(posedge clk); rst<=0; @(posedge clk);
        // directed corners: equal, max-positive, and borrow (x<y) cases
        drive(0,0); drive(Q-1,Q-1); drive(Q-1,0); drive(0,Q-1);
        drive(1,2); drive(2,1); drive(5,5); drive(0,1); drive(12288,12288);
        for (i=0;i<NTEST;i=i+1) begin rx=$random; ry=$random; drive(rx%Q, ry%Q); end
        @(posedge clk); in_valid<=0; repeat(8) @(posedge clk);
        $display("=== rns_sub  [(x-y) mod 12289] ===");
        $display(" checked=%0d  mismatches=%0d  latency=%0d cyc", n, errors, first_out-first_in);
        if (errors==0) $display(" RESULT: PASS"); else $display(" RESULT: FAIL");
        $finish;
    end
endmodule
