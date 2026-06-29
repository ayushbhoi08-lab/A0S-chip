// ============================================================================
// Ansh-108 Core -- Path A, Session S5 : DEEPER formal sign-off for core_top.
//   These EXTEND the S4 set (quiet/bindu/tick/latmul/latfold in core_top_formal.v)
//   to CLOSE the Phase-2 formal gate. CONTROL-PLANE only -- no numeric/modulo
//   reference appears anywhere, so there is no modulo-reference solver wall (that
//   wall, hit in S3, means datapath NUMERIC correctness is owned by the exhaustive
//   Python legs + the already-proven reused cores; formal proves the control the
//   integration adds). Proved by sby + boolector in seconds each.
//
//   S4 pinned the latency of the longest op (MUL=5) and the stream op (FOLD=2).
//   S5 pins EVERY remaining gated op's latency, plus the control-safety invariants
//   the result FSM must satisfy:
//     * LATADD  : ADD  out_valid is EXACTLY accept delayed 3  (rns_add 2 + 1 reg)
//     * LATSUB  : SUB  out_valid is EXACTLY accept delayed 3  (rns_sub 2 + 1 reg)
//     * LATRED  : RED  out_valid is EXACTLY accept delayed 2  (rns_reduce 1 + 1)
//     * LATVER  : VER  out_valid is EXACTLY accept delayed 2  (rns_verify 1 + 1)
//     * LATTICK : R_T  out_valid is EXACTLY accept delayed 2  (rt_ov 1 + 1)
//     * INTERLOCK : at most ONE gated op in flight (outstanding count <= 1); the
//                   same invariant catches a spurious gated result (underflow wraps
//                   the 2-bit count to >=2). Proves the single-in-flight busy gate.
//     * READY   : await-read contract -- once result_ready is set it STAYS set
//                 until read_ack OR a new gated accept (the only two clears).
//     * RESERVED: opcodes 9..14 (host-side cmp/bitwise in Path A) are inert --
//                 no out_valid, no busy, no result_ready, no bindu, ever.
//   Each is a separate top so sby selects it with prep -top (no parameters).
// ============================================================================

// ---- latency-exactness harness, one per gated op (mirrors S4 ctf_latmul) ----

module ctf_latadd (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28]==4'd1);              // ADD
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & ~busy & ~rst;        // gated: accepted only when ~busy
    reg a1,a2,a3;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0;a3<=0; end
        else begin a1<=accept; a2<=a1; a3<=a2; end
    end
    always @(posedge clk) if (started) assert(out_valid==a3);   // ADD latency = 3
endmodule

module ctf_latsub (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28]==4'd2);              // SUB
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & ~busy & ~rst;
    reg a1,a2,a3;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0;a3<=0; end
        else begin a1<=accept; a2<=a1; a3<=a2; end
    end
    always @(posedge clk) if (started) assert(out_valid==a3);   // SUB latency = 3
endmodule

module ctf_latred (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28]==4'd3);              // REDUCE
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & ~busy & ~rst;
    reg a1,a2;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0; end
        else begin a1<=accept; a2<=a1; end
    end
    always @(posedge clk) if (started) assert(out_valid==a2);   // REDUCE latency = 2
endmodule

module ctf_latver (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28]==4'd5);              // VERIFY
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & ~busy & ~rst;
    reg a1,a2;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0; end
        else begin a1<=accept; a2<=a1; end
    end
    always @(posedge clk) if (started) assert(out_valid==a2);   // VERIFY latency = 2
endmodule

module ctf_lattick (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28]==4'd6);              // READ_TICK
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & ~busy & ~rst;
    reg a1,a2;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0; end
        else begin a1<=accept; a2<=a1; end
    end
    always @(posedge clk) if (started) assert(out_valid==a2);   // READ_TICK latency = 2
endmodule

// ---- single-in-flight interlock: outstanding gated ops <= 1 -----------------
//   Packets are gated-or-idle (opcode in {MUL,ADD,SUB,REDUCE,VERIFY,READ_TICK})
//   so out_valid is purely gated. A 2-bit shadow counts accepted-not-yet-returned
//   ops: +1 on a gated accept, -1 on out_valid. assert(<=1) proves single in
//   flight AND (via 2-bit underflow wrapping to 3) that no out_valid fires without
//   a matching accept. Operand values are left FREE -- the pipeline latency is
//   data-independent, so this is the full control proof.
module ctf_interlock (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    wire [3:0] op = packet[31:28];
    wire op_gated = (op==4'd0)|(op==4'd1)|(op==4'd2)|(op==4'd3)|(op==4'd5)|(op==4'd6);
    always @(posedge clk) begin
        assume(op_gated);                          // gated-or-idle only (no fold/ff)
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & op_gated & ~busy & ~rst;
    reg [1:0] outst;
    always @(posedge clk) begin
        if (rst) outst <= 2'd0;
        else     outst <= outst + (accept ? 2'd1 : 2'd0) - (out_valid ? 2'd1 : 2'd0);
    end
    always @(posedge clk) if (started) assert(outst <= 2'd1);
endmodule

// ---- await-read contract: result_ready holds until read or a new accept -----
//   The ONLY clears of result_ready are read_ack and a new gated accept. Prove:
//   if it was set last cycle and neither happened, it is still set now (the host
//   may take as long as it likes to read). Arbitrary mixed packets allowed.
module ctf_ready (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) if (started) assume(rst==1'b0);
    wire [3:0] op = packet[31:28];
    wire op_gated = (op==4'd0)|(op==4'd1)|(op==4'd2)|(op==4'd3)|(op==4'd5)|(op==4'd6);
    wire acc_g = in_valid & op_gated & ~busy & ~rst;
    reg pr_ready, pr_read, pr_acc;
    always @(posedge clk) begin
        if (rst) begin pr_ready<=0; pr_read<=0; pr_acc<=0; end
        else     begin pr_ready<=result_ready; pr_read<=read_ack; pr_acc<=acc_g; end
    end
    // held last cycle, not read, no new accept -> still held now
    always @(posedge clk) if (started)
        if (pr_ready & ~pr_read & ~pr_acc) assert(result_ready);
endmodule

// ---- reserved opcodes 9..14 are inert (Path-A host-side slots) ---------------
module ctf_reserved (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28] >= 4'd9 && packet[31:28] <= 4'd14);   // reserved slots
        if (started) assume(rst==1'b0);
    end
    // no select fires -> no accept, no result, no bindu, ever
    always @(posedge clk) if (started) begin
        assert(out_valid    == 1'b0);
        assert(busy         == 1'b0);
        assert(result_ready == 1'b0);
        assert(bindu        == 1'b0);
    end
endmodule
