// Formal harness for rns108. Properties proved by SAT/SMT (sby/boolector),
// NOT simulated samples. x,y,in_valid,rst are free (unconstrained) primary
// inputs -- the solver explores every possible value at every time step.
// Design has NO feedback beyond its fixed 4-stage pipeline, so a BMC depth
// past the pipeline length is a COMPLETE proof, not a bounded approximation.
module rns108_formal (
    input clk,
    input rst,
    input in_valid,
    input [6:0] x,
    input [6:0] y
);
    wire out_valid;
    wire [6:0] out;

    rns108 dut (
        .clk(clk), .rst(rst), .in_valid(in_valid),
        .x(x), .y(y), .out_valid(out_valid), .out(out)
    );

    // restrict to the DUT's documented legal domain (0..107), same domain
    // Phase-2's exhaustive sim covered -- not overreaching past the spec.
    always @(posedge clk) begin
        assume (x < 108);
        assume (y < 108);
    end

    // force a known reset at the initial state only -- rst is free afterward,
    // so the proof also covers arbitrary later resets, not just power-on.
    initial assume (rst);

    // standard FV idiom: every reg (DUT-internal AND shadow) is genuinely
    // unconstrained "garbage" at t=0, since none has an explicit reset value
    // in the (already-verified, untouched) RTL -- a single rst=1 input only
    // determines what regs become AFTER the first clock edge, not their raw
    // initial content. Don't check properties until one clock has passed.
    reg started = 1'b0;
    always @(posedge clk) started <= 1'b1;

    // ---- Property 1: SAFETY -- output is always a valid mod-108 value ----
    always @(posedge clk) if (started) assert (out < 108);

    // ---- Property 2: LATENCY -- out_valid is exactly 4 cycles behind in_valid,
    //      for ANY input/reset sequence (shadow chain mirrors DUT's own rst gating) ----
    reg v1, v2, v3, v4;
    always @(posedge clk) begin
        v1 <= rst ? 1'b0 : in_valid;
        v2 <= rst ? 1'b0 : v1;
        v3 <= rst ? 1'b0 : v2;
        v4 <= rst ? 1'b0 : v3;
    end
    always @(posedge clk) if (started) assert (out_valid == v4);

    // ---- Property 3: FUNCTIONAL CORRECTNESS -- out matches the true CRT
    //      transform for every input, shadowed through the same 4-stage delay ----
    function [6:0] gold(input [6:0] xx, input [6:0] yy);
        integer a, b;
        begin
            a = ((xx % 4)  * (yy % 4))  % 4;
            b = ((xx % 27) * (yy % 27)) % 27;
            gold = (81*a + 28*b) % 108;
        end
    endfunction

    reg [6:0] g1, g2, g3, g4;
    always @(posedge clk) begin
        g1 <= gold(x, y);
        g2 <= g1;
        g3 <= g2;
        g4 <= g3;
    end
    always @(posedge clk) if (started && v4) assert (out == g4);

endmodule
