// Formal harness for rns_verify. Properties proved by SAT/SMT (sby), NOT sampled.
// Feedback-free 1-stage pipeline -> a BMC depth past the pipeline is a COMPLETE proof.
module rns_verify_formal (
    input clk, input rst, input in_valid,
    input [13:0] x, input [13:0] y
);
    wire out_valid; wire out_eq;
    rns_verify dut(.clk(clk), .rst(rst), .in_valid(in_valid),
                   .x(x), .y(y), .out_valid(out_valid), .out_eq(out_eq));

    // legal operand domain (matches the lane); equality is well-defined for any
    // pair, but we keep the same <q domain the other lane ops assume.
    always @(posedge clk) begin assume (x < 12289); assume (y < 12289); end

    initial assume (rst);
    reg started = 1'b0;
    always @(posedge clk) started <= 1'b1;

    // ---- P2 LATENCY: out_valid is exactly 1 cycle behind in_valid ----
    reg v1;
    always @(posedge clk) v1 <= rst ? 1'b0 : in_valid;
    always @(posedge clk) if (started) assert (out_valid == v1);

    // ---- P3 FUNCTIONAL CORRECTNESS: out_eq == (x==y), shadowed 1 stage ----
    reg g1;
    always @(posedge clk) g1 <= (x == y);
    always @(posedge clk) if (started) assert (out_eq == g1);
endmodule
