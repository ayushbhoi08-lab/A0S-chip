// Formal harness for rns41580p (DEEP-PIPELINED 5-dial core). Same CRT-complete
// proof strategy as rns41580_formal.v -- per-track residue checks (no 16x16
// multiply for the solver) -- but mirrors the 6-cycle pipeline latency.
//   P1: out < 41580                              (bounded)
//   P2: out_valid is exactly 6 cycles behind in_valid
//   P3: out === (x_i*y_i) (mod m_i) for all 5 dials
// (out == (rx*ry)%41580 then follows from the CRT bijection proven exhaustively
//  over all 41,580 states in verify_crt_5mod.py -- a layered proof.)
module rns41580p_formal (
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

    rns41580p dut(.clk(clk), .rst(rst), .in_valid(in_valid),
        .x4(x4), .y4(y4), .x27(x27), .y27(y27), .x5(x5), .y5(y5),
        .x7(x7), .y7(y7), .x11(x11), .y11(y11),
        .out_valid(out_valid), .out(out));

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

    // ---- P1 SAFETY (valid outputs are in range) ----
    //   Gated on out_valid: the split-reduce pipeline only guarantees out<M for
    //   real data that has traversed the reset-cleared pipeline. Power-on garbage
    //   in the separate sum_5/q_5 registers is a don't-care (out_valid=0) and is
    //   correctly excluded -- P2 below proves out_valid's timing independently.
    always @(posedge clk) if (started && out_valid) assert (out < 41580);

    // ---- P2 LATENCY: out_valid exactly 6 cycles behind in_valid ----
    reg v1, v2, v3, v4, v5, v6;
    always @(posedge clk) begin
        v1 <= rst ? 1'b0 : in_valid;
        v2 <= rst ? 1'b0 : v1;
        v3 <= rst ? 1'b0 : v2;
        v4 <= rst ? 1'b0 : v3;
        v5 <= rst ? 1'b0 : v4;
        v6 <= rst ? 1'b0 : v5;
    end
    always @(posedge clk) if (started) assert (out_valid == v6);

    // ---- P3 CORRECTNESS (per-track, CRT-complete) ----
    wire [4:0] e4  = (x4  * y4 ) % 4;
    wire [9:0] e27 = (x27 * y27) % 27;
    wire [4:0] e5  = (x5  * y5 ) % 5;
    wire [5:0] e7  = (x7  * y7 ) % 7;
    wire [6:0] e11 = (x11 * y11) % 11;

    // align expected residues to the DUT's 6-cycle latency
    reg [4:0] e4_1,e4_2,e4_3,e4_4,e4_5,e4_6;
    reg [9:0] e27_1,e27_2,e27_3,e27_4,e27_5,e27_6;
    reg [4:0] e5_1,e5_2,e5_3,e5_4,e5_5,e5_6;
    reg [5:0] e7_1,e7_2,e7_3,e7_4,e7_5,e7_6;
    reg [6:0] e11_1,e11_2,e11_3,e11_4,e11_5,e11_6;
    always @(posedge clk) begin
        e4_1<=e4;   e4_2<=e4_1;   e4_3<=e4_2;   e4_4<=e4_3;   e4_5<=e4_4;   e4_6<=e4_5;
        e27_1<=e27; e27_2<=e27_1; e27_3<=e27_2; e27_4<=e27_3; e27_5<=e27_4; e27_6<=e27_5;
        e5_1<=e5;   e5_2<=e5_1;   e5_3<=e5_2;   e5_4<=e5_3;   e5_5<=e5_4;   e5_6<=e5_5;
        e7_1<=e7;   e7_2<=e7_1;   e7_3<=e7_2;   e7_4<=e7_3;   e7_5<=e7_4;   e7_6<=e7_5;
        e11_1<=e11; e11_2<=e11_1; e11_3<=e11_2; e11_4<=e11_3; e11_5<=e11_4; e11_6<=e11_5;
    end

    always @(posedge clk) if (started && v6) begin
        assert ((out % 4)  == e4_6);
        assert ((out % 27) == e27_6);
        assert ((out % 5)  == e5_6);
        assert ((out % 7)  == e7_6);
        assert ((out % 11) == e11_6);
    end

endmodule
