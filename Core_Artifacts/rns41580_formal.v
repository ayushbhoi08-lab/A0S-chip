// Formal harness for rns41580 (5-modulus Ansh-N core).
// Properties proved by SAT/SMT (sby/boolector) over ALL residue inputs, not
// sampled. Free inputs, feed-forward pipeline -> BMC past pipeline depth is a
// complete proof.
//
// ---------------------------------------------------------------------------
// PROOF STRATEGY (why P3 is split into 5 small-modulus checks):
//   The naive spec  out == (rx*ry) % 41580  forces the solver to bit-blast a
//   16x16 variable multiply + a 32-bit modulo -- the multiplier-equivalence
//   wall; boolector does not converge on it.
//   By CRT, Z/41580 ~= Z/4 x Z/27 x Z/5 x Z/7 x Z/11 is a BIJECTION, so for
//   a,b in [0,41580):  a == b  <=>  a===b (mod m_i) for every track m_i.
//   Also (rx*ry mod M) mod m_i = (rx mod m_i)*(ry mod m_i) mod m_i
//                              = (x_i * y_i) mod m_i              (since the
//   idempotent reconstruction gives rx === x_i (mod m_i)).
//   Therefore the strong spec is EQUIVALENT to:
//        P1:  out < 41580                       (bounded)
//        P3:  out === (x_i*y_i) (mod m_i)  for all 5 tracks
//   Each P3 check is tiny (product <=676, modulus <=27) -> SMT-trivial.
//   The final out == (rx*ry)%M equality then follows from CRT uniqueness,
//   which is proven EXHAUSTIVELY over all 41,580 states in verify_crt_5mod.py.
//   (Layered proof: SMT proves the divider-free hardware matches small-modulus
//    arithmetic; the offline bijection proof supplies the multiply.)
// ---------------------------------------------------------------------------
module rns41580_formal (
    input            clk,
    input            rst,
    input            in_valid,
    input     [1:0]  x4,  y4,
    input     [4:0]  x27, y27,
    input     [2:0]  x5,  y5,
    input     [2:0]  x7,  y7,
    input     [3:0]  x11, y11
);
    wire out_valid;
    wire [15:0] out;

    rns41580 dut(.clk(clk), .rst(rst), .in_valid(in_valid),
        .x4(x4), .y4(y4), .x27(x27), .y27(y27), .x5(x5), .y5(y5),
        .x7(x7), .y7(y7), .x11(x11), .y11(y11),
        .out_valid(out_valid), .out(out));

    // restrict each track to its legal residue domain
    always @(posedge clk) begin
        assume (x4  < 4);  assume (y4  < 4);
        assume (x27 < 27); assume (y27 < 27);
        assume (x5  < 5);  assume (y5  < 5);
        assume (x7  < 7);  assume (y7  < 7);
        assume (x11 < 11); assume (y11 < 11);
    end

    initial assume (rst);
    reg started = 1'b0;
    always @(posedge clk) started <= 1'b1;

    // ---- P1 SAFETY: output always a valid mod-41580 value ----
    always @(posedge clk) if (started) assert (out < 41580);

    // ---- P2 LATENCY: out_valid is exactly 4 cycles behind in_valid ----
    reg v1, v2, v3, v4;
    always @(posedge clk) begin
        v1 <= rst ? 1'b0 : in_valid;
        v2 <= rst ? 1'b0 : v1;
        v3 <= rst ? 1'b0 : v2;
        v4 <= rst ? 1'b0 : v3;
    end
    always @(posedge clk) if (started) assert (out_valid == v4);

    // ---- P3 CORRECTNESS (per-track, CRT-complete): out === x_i*y_i (mod m_i) ----
    //   Expected product residues -- tiny products, constant-modulus reduce.
    //   (TB/gold MAY divide; only the DUT must be divider-free.)
    wire [4:0] e4  = (x4  * y4 ) % 4;    // product <= 9
    wire [9:0] e27 = (x27 * y27) % 27;   // product <= 676
    wire [4:0] e5  = (x5  * y5 ) % 5;    // product <= 16
    wire [5:0] e7  = (x7  * y7 ) % 7;    // product <= 36
    wire [6:0] e11 = (x11 * y11) % 11;   // product <= 100

    // align expected residues to the DUT's 4-cycle latency
    reg [4:0] e4_1,e4_2,e4_3,e4_4;
    reg [9:0] e27_1,e27_2,e27_3,e27_4;
    reg [4:0] e5_1,e5_2,e5_3,e5_4;
    reg [5:0] e7_1,e7_2,e7_3,e7_4;
    reg [6:0] e11_1,e11_2,e11_3,e11_4;
    always @(posedge clk) begin
        e4_1<=e4;   e4_2<=e4_1;   e4_3<=e4_2;   e4_4<=e4_3;
        e27_1<=e27; e27_2<=e27_1; e27_3<=e27_2; e27_4<=e27_3;
        e5_1<=e5;   e5_2<=e5_1;   e5_3<=e5_2;   e5_4<=e5_3;
        e7_1<=e7;   e7_2<=e7_1;   e7_3<=e7_2;   e7_4<=e7_3;
        e11_1<=e11; e11_2<=e11_1; e11_3<=e11_2; e11_4<=e11_3;
    end

    // residues of the divider-free DUT output (constant-modulus reduce of a
    // bounded 16-bit value -> SMT-easy, no variable*variable multiply anywhere)
    always @(posedge clk) if (started && v4) begin
        assert ((out % 4)  == e4_4);
        assert ((out % 27) == e27_4);
        assert ((out % 5)  == e5_4);
        assert ((out % 7)  == e7_4);
        assert ((out % 11) == e11_4);
    end

endmodule
