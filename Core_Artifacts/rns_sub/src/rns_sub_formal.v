// Formal harness for rns_sub. Properties proved by SAT/SMT (sby), NOT sampled.
// x,y,in_valid,rst are free primary inputs -- the solver explores every value at
// every step. No feedback beyond the fixed 2-stage pipeline, so a BMC depth past
// the pipeline length is a COMPLETE proof. SUB has no wide-multiply wall, so FULL
// CORRECTNESS (P3) is proven here directly -- including the borrow-correction
// path where the 14-bit add wraps (out == (x-y) mod q must hold for ALL x<y too).
module rns_sub_formal (
    input clk, input rst, input in_valid,
    input [13:0] x, input [13:0] y
);
    wire out_valid; wire [13:0] out;
    rns_sub dut(.clk(clk), .rst(rst), .in_valid(in_valid),
                .x(x), .y(y), .out_valid(out_valid), .out(out));

    // documented legal domain (operands in [0,q)), same as the sim covers
    always @(posedge clk) begin assume (x < 12289); assume (y < 12289); end

    // known reset only at the initial state; rst free afterward (covers later resets)
    initial assume (rst);

    // don't check until one clock has passed (regs are uninitialised garbage at t=0)
    reg started = 1'b0;
    always @(posedge clk) started <= 1'b1;

    // ---- P1 RANGE: valid output is always a legal mod-q value ----
    always @(posedge clk) if (started && out_valid) assert (out < 12289);

    // ---- P2 LATENCY: out_valid is exactly 2 cycles behind in_valid ----
    reg v1, v2;
    always @(posedge clk) begin
        v1 <= rst ? 1'b0 : in_valid;
        v2 <= rst ? 1'b0 : v1;
    end
    always @(posedge clk) if (started) assert (out_valid == v2);

    // ---- P3 FUNCTIONAL CORRECTNESS: out == (x-y) mod q, shadowed 2 stages ----
    // gold uses signed math so the modulo of a negative difference is the true
    // least-nonnegative residue -- exactly what branch-free borrow-correct must hit.
    function [13:0] gold(input [13:0] xx, input [13:0] yy);
        integer d;
        begin
            d = xx - yy;
            if (d < 0) d = d + 12289;
            gold = d[13:0];
        end
    endfunction
    reg [13:0] g1, g2;
    always @(posedge clk) begin
        g1 <= gold(x, y);
        g2 <= g1;
    end
    always @(posedge clk) if (started && v2) assert (out == g2);
endmodule
