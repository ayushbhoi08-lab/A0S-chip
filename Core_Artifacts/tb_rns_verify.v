`timescale 1ns/1ps
// Self-checking TB for rns_verify: ~300k pairs (half forced equal) checked
// against (x==y); measures 1-cycle latency.
module tb;
    localparam integer Q = 12289;
    localparam integer NTEST = 300000;
    reg clk=0, rst=1, in_valid=0;
    reg [13:0] x, y;
    wire out_valid, out_eq;
    rns_verify dut(.clk(clk),.rst(rst),.in_valid(in_valid),.x(x),.y(y),
                   .out_valid(out_valid),.out_eq(out_eq));
    always #0.5 clk=~clk;

    // mirror DUT 1-cycle latency
    reg [13:0] cx=0, cy=0;
    reg e1; reg ev1;
    always @(posedge clk) begin
        e1  <= (cx == cy);
        ev1 <= rst ? 1'b0 : in_valid;
    end

    integer cyc=0; always @(posedge clk) cyc=cyc+1;
    integer n=0, errors=0, neq=0, first_in=-1, first_out=-1;
    always @(posedge clk) begin
        if (in_valid && first_in<0) first_in=cyc;
        if (out_valid && first_out<0) first_out=cyc;
        if (out_valid) begin n=n+1; if (out_eq) neq=neq+1;
            if (out_eq !== e1) begin errors=errors+1;
                if (errors<=5) $display("  MISMATCH n=%0d out_eq=%0b exp=%0b", n, out_eq, e1); end
        end
    end

    task drive(input [13:0] xi, input [13:0] yi);
        begin @(posedge clk); in_valid<=1; cx<=xi; cy<=yi; x<=xi; y<=yi; end
    endtask

    integer i; reg [31:0] rx, ry;
    initial begin
        repeat(4) @(posedge clk); rst<=0; @(posedge clk);
        drive(0,0); drive(0,1); drive(Q-1,Q-1); drive(Q-1,Q-2); drive(7,7); drive(7,8);
        for (i=0;i<NTEST;i=i+1) begin
            rx=$random;
            if (i[0]) ry=rx;            // half the pairs forced equal
            else      ry=$random;
            drive(rx%Q, ry%Q);
        end
        @(posedge clk); in_valid<=0; repeat(8) @(posedge clk);
        $display("=== rns_verify  [x==y -> flag] ===");
        $display(" checked=%0d  equal-flagged=%0d  mismatches=%0d  latency=%0d cyc",
                 n, neq, errors, first_out-first_in);
        if (errors==0) $display(" RESULT: PASS"); else $display(" RESULT: FAIL");
        $finish;
    end
endmodule
