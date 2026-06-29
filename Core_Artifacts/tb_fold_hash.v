`timescale 1ns/1ps
// Self-checking TB for fold_hash: a parallel software-style Horner accumulator
// (using %) tracks the DUT's running hash cycle-by-cycle through random folds,
// flushes and bubbles. Also runs the golden_model's directed feet [5,9,12292]
// (last term > q, exercising the reducer). Checks h every cycle; latency = 1.
module tb;
    localparam integer Q = 12289;
    localparam [13:0] SEED = 14'd1;
    localparam integer NTEST = 200000;

    reg clk=0, rst=1, flush=0, fold_en=0;
    reg [27:0] data=0;
    wire out_valid; wire [13:0] h;
    fold_hash dut(.clk(clk),.rst(rst),.flush(flush),.fold_en(fold_en),
                  .data(data),.out_valid(out_valid),.h(h));
    always #0.5 clk=~clk;

    // true Horner update (TB may use *,%,wide ints; the DUT must not)
    function [13:0] gold(input [13:0] hh, input [27:0] dd);
        reg [63:0] t;
        begin t = hh*108 + dd; gold = t % Q; end
    endfunction

    // parallel reference accumulator + valid, same rules / same cycle as the DUT
    reg [13:0] gh = SEED; reg gv = 0;
    always @(posedge clk) begin
        if (rst || flush)  gh <= SEED;
        else if (fold_en)  gh <= gold(gh, data);
        gv <= rst ? 1'b0 : (fold_en & ~flush);
    end

    integer cyc=0; always @(posedge clk) cyc=cyc+1;
    integer chkn=0, errors=0, first_fe=-1, first_ov=-1;
    reg chk=0;
    always @(posedge clk) if (!rst) chk<=1;   // start checking after reset
    always @(posedge clk) begin
        if (fold_en && first_fe<0) first_fe=cyc;
        if (out_valid && first_ov<0) first_ov=cyc;
        if (chk) begin
            chkn=chkn+1;
            if (h !== gh) begin errors=errors+1;
                if (errors<=5) $display("  H MISMATCH cyc=%0d h=%0d exp=%0d", cyc, h, gh); end
            if (out_valid !== gv) begin errors=errors+1;
                if (errors<=5) $display("  VALID MISMATCH cyc=%0d ov=%0b exp=%0b", cyc, out_valid, gv); end
        end
    end

    task step(input fe, input fl, input [27:0] d);
        begin @(posedge clk); fold_en<=fe; flush<=fl; data<=d; end
    endtask

    integer i; reg [31:0] rr; reg [13:0] hfeet;
    initial begin
        repeat(4) @(posedge clk); rst<=0; @(posedge clk);

        // directed: golden_model feet [5,9,12292], back-to-back, after a flush
        step(0,1,0);                       // reseed
        step(1,0,5); step(1,0,9); step(1,0,28'd12292);
        step(0,0,0);                       // settle
        @(posedge clk);
        hfeet = gold(gold(gold(SEED,5),9),28'd12292);
        $display(" feet[5,9,12292] -> h=%0d (manual Horner=%0d)", h, hfeet);

        // randomized stream: folds, periodic flush, periodic bubble
        for (i=0;i<NTEST;i=i+1) begin
            rr=$random;
            if (i%4096==0)        step(0,1,0);            // flush
            else if (rr[1:0]==0)  step(0,0,rr[27:0]);     // bubble (hold)
            else                  step(1,0,rr[27:0]);     // fold
        end
        step(0,0,0); repeat(8) @(posedge clk);

        $display("=== fold_hash  [h<-(h*108+data) mod 12289] ===");
        $display(" cycles checked=%0d  mismatches=%0d  latency=%0d cyc",
                 chkn, errors, first_ov-first_fe);
        if (errors==0) $display(" RESULT: PASS"); else $display(" RESULT: FAIL");
        $finish;
    end
endmodule
