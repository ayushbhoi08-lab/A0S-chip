// Range + latency proof. P1 gated on out_valid: Barrett guarantees the
// registered intermediate r3 in [0,2q) only for real data, so out<q holds for
// VALID outputs (power-on garbage in r3 is a don't-care). Full correctness
// (out==(x*y)%q) is proven EXHAUSTIVELY in barrett_check.c (all 12289^2 pairs).
module ntt_mul12289_formal(input clk, input rst, input in_valid,
                           input [13:0] x, input [13:0] y, output dummy);
    wire out_valid; wire [13:0] out;
    assign dummy=1'b0;
    ntt_mul12289 dut(.clk(clk),.rst(rst),.in_valid(in_valid),.x(x),.y(y),
                     .out_valid(out_valid),.out(out));
    always @(posedge clk) begin assume(x<12289); assume(y<12289); end
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) if (started && out_valid) assert (out < 12289);  // P1 range (valid)
    reg v1,v2,v3,v4;
    always @(posedge clk) begin
        v1<=rst?1'b0:in_valid; v2<=rst?1'b0:v1; v3<=rst?1'b0:v2; v4<=rst?1'b0:v3;
    end
    always @(posedge clk) if (started) assert (out_valid==v4);    // P2 latency
endmodule
