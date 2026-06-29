// BONUS attempt: full correctness out==(x*y)%q via SMT (14x14 multiply -> may
// hit the multiplier wall; run with bitwuzla + time budget). barrett_check.c is
// the authoritative exhaustive proof regardless.
module ntt_mul12289_corr(input clk, input rst, input in_valid,
                         input [13:0] x, input [13:0] y, output dummy);
    wire out_valid; wire [13:0] out;
    assign dummy=1'b0;
    ntt_mul12289 dut(.clk(clk),.rst(rst),.in_valid(in_valid),.x(x),.y(y),
                     .out_valid(out_valid),.out(out));
    always @(posedge clk) begin assume(x<12289); assume(y<12289); end
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    reg v1,v2,v3,v4;
    always @(posedge clk) begin
        v1<=rst?1'b0:in_valid; v2<=rst?1'b0:v1; v3<=rst?1'b0:v2; v4<=rst?1'b0:v3;
    end
    wire [27:0] prod = x*y;
    wire [13:0] g = prod % 12289;
    reg [13:0] g1,g2,g3,g4;
    always @(posedge clk) begin g1<=g; g2<=g1; g3<=g2; g4<=g3; end
    always @(posedge clk) if (started && v4) assert (out == g4);
endmodule
