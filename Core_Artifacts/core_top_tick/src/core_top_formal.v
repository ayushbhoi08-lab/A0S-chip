// ============================================================================
// Formal harness(es) for core_top (S4). CONTROL-PLANE properties only -- proved
// by SAT/SMT (sby + boolector). NO numeric/modulo reference appears here, so
// there is no modulo-reference solver wall (that wall, hit in S3, means datapath
// NUMERIC correctness is owned by the exhaustive Python legs + the already-proven
// reused cores; formal here proves the FSM/control the integration adds):
//   * QUIET   : no spurious results -- with no packets, nothing ever fires.
//   * BINDU   : bindu is exactly a registered (RESET packet) -> fires once each.
//   * TICK_WP : the tick free-runs identically regardless of any packet (write-
//               protected / "can't lie"): it equals an input-independent shadow.
//   * LATMUL  : valid-output gating + latency exactness for the longest op (MUL):
//               out_valid is EXACTLY accept delayed 5 (datapath 4 + 1 output reg).
//   * LATFOLD : latency exactness for the streaming op (FOLD): out_valid is
//               EXACTLY accept delayed 2 (datapath 1 + 1 output reg).
// Each is a separate top so sby can select it with prep -top (no parameters).
// ============================================================================

// ---- shared DUT wrapper macro-style instantiation is inlined per module ---- //

module ctf_quiet (input clk, input rst, input read_ack);
    // no packets ever: in_valid tied 0
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(1'b0),.packet(32'b0),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) if (started) begin
        assert(out_valid==1'b0);
        assert(bindu==1'b0);
        assert(busy==1'b0);
        assert(result_ready==1'b0);
    end
endmodule

module ctf_bindu (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    // bindu must equal a registered "RESET packet accepted" (RESET is fire-forget,
    // accepted whenever in_valid & opcode==15) -> exactly one pulse per RESET packet.
    reg ar; always @(posedge clk) ar <= rst ? 1'b0 : (in_valid & (packet[31:28]==4'd15));
    always @(posedge clk) if (started) assert(bindu==ar);
endmodule

module ctf_tick (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    // input-independent shadow of the free-running tick (no packet term anywhere)
    reg [7:0] s0; reg [4:0] s1; reg [9:0] s2;
    always @(posedge clk) begin
        if (rst) begin s0<=8'd0; s1<=5'd0; s2<=10'd0; end
        else begin
            s0 <= s0 + 8'd1;
            s1 <= (s1==5'd26)  ? 5'd0  : s1+5'd1;
            s2 <= (s2==10'd624)? 10'd0 : s2+10'd1;
        end
    end
    // tick equals the shadow for EVERY packet stream -> write-protected / can't-lie
    always @(posedge clk) if (started) begin
        assert(t0==s0); assert(t1==s1); assert(t2==s2);
    end
endmodule

module ctf_latmul (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    // every packet is a legal MUL; rst only at the initial state
    always @(posedge clk) begin
        assume(packet[31:28]==4'd0);
        assume(packet[13:0]   < 14'd12289);
        assume(packet[27:14]  < 14'd12289);
        if (started) assume(rst==1'b0);
    end
    // MUL accepted only when ~busy (single in-flight) and not during reset
    wire accept = in_valid & ~busy & ~rst;
    reg a1,a2,a3,a4,a5;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0;a3<=0;a4<=0;a5<=0; end
        else begin a1<=accept; a2<=a1; a3<=a2; a4<=a3; a5<=a4; end
    end
    // valid-output gating + latency exactness: out_valid IFF a MUL accepted 5 ago
    always @(posedge clk) if (started) assert(out_valid==a5);
endmodule

module ctf_latfold (input clk, input rst, input in_valid, input [31:0] packet, input read_ack);
    wire [22:0] out; wire out_valid, result_ready, busy, bindu;
    wire [3:0] oe; wire [1:0] rm; wire [7:0] t0; wire [4:0] t1; wire [9:0] t2;
    core_top dut(.clk(clk),.rst(rst),.in_valid(in_valid),.packet(packet),.read_ack(read_ack),
        .out(out),.out_valid(out_valid),.result_ready(result_ready),.busy(busy),
        .bindu(bindu),.opcode_echo(oe),.res_mode(rm),.tick0(t0),.tick1(t1),.tick2(t2));
    initial assume(rst);
    reg started=1'b0; always @(posedge clk) started<=1'b1;
    always @(posedge clk) begin
        assume(packet[31:28]==4'd4);             // FOLD
        if (started) assume(rst==1'b0);
    end
    wire accept = in_valid & ~rst;               // FOLD streams (not busy-gated)
    reg a1,a2;
    always @(posedge clk) begin
        if (rst) begin a1<=0;a2<=0; end
        else begin a1<=accept; a2<=a1; end
    end
    // latency exactness for the stream op: out_valid IFF a FOLD accepted 2 ago
    always @(posedge clk) if (started) assert(out_valid==a2);
endmodule
