// Formal harness for fold_hash. Properties proved by SAT/SMT (sby + boolector).
//
// SCOPE NOTE (honest, per the arc's ntt precedent): formal here proves the
// CONTROL + RANGE properties (latency, reseed, h always in range). FULL NUMERIC
// correctness -- h == (h*108+data) mod q -- is OWNED BY THE EXHAUSTIVE PYTHON LEG,
// which proves barrett28(a)==a mod q for ALL 2^28 inputs; the fold then follows by
// the identity (a mod q + b mod q) mod q = (a+b) mod q. An all-input SMT proof of
// that equality hit the modulo-reference solver wall (a `% q` reference over free
// 28-bit data stalls boolector AND bitwuzla for >1h), the same class of wall the
// ntt 14x14 core hit and the arc resolved with exhaustive checking (barrett_check.c).
module fold_hash_formal (
    input clk, input rst, input flush, input fold_en,
    input [27:0] data
);
    wire out_valid; wire [13:0] h;
    fold_hash dut(.clk(clk), .rst(rst), .flush(flush), .fold_en(fold_en),
                  .data(data), .out_valid(out_valid), .h(h));

    initial assume (rst);
    reg started = 1'b0;
    always @(posedge clk) started <= 1'b1;

    // ---- P1 RANGE: the running hash is ALWAYS a legal mod-q value ----
    always @(posedge clk) if (started) assert (h < 12289);

    // ---- P2 LATENCY: out_valid mirrors a registered (fold_en & ~flush) ----
    reg ev;
    always @(posedge clk) ev <= rst ? 1'b0 : (fold_en & ~flush);
    always @(posedge clk) if (started) assert (out_valid == ev);

    // ---- P3 RESEED: rst or flush forces the seed (control correctness) ----
    reg pflush, prst;
    always @(posedge clk) begin pflush <= flush; prst <= rst; end
    always @(posedge clk)
        if (started && (prst || pflush))
            assert (h == 14'd1);

    // (Numeric correctness  h == (h*108+data) mod q  is the exhaustive Python leg;
    //  see the scope note above -- the % reference is an SMT wall over free data.)
endmodule
