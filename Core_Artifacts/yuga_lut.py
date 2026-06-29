# Yuga Mapping: Mahayuga (4,320,000 yr) -> 108-state loop, Vipala-resolution LUT.
from fractions import Fraction

VIPALA_S  = Fraction(16, 1000)          # 0.016 s  (user-specified resolution; canonical vipala=0.4s)
YEAR_S    = 365.25 * 86400              # Julian year = 31,557,600 s
MAHAYUGA_Y = 4_320_000
STATES    = 108
F_CLK     = 157_900_000                 # measured routed fmax, Hz

T_MY_s    = MAHAYUGA_Y * YEAR_S                          # Mahayuga in seconds
N_total   = int(T_MY_s / float(VIPALA_S))               # total Vipalas
# exact integer path:
T_MY_s_i  = MAHAYUGA_Y * 31_557_600
N_total   = T_MY_s_i * 1000 // 16                        # /0.016 exactly
K_state   = N_total // STATES                            # Yuga Step (Vipalas / state)
assert K_state * STATES == N_total

print("T_MY (s)        =", T_MY_s_i)
print("N_total Vipalas =", N_total)
print("counter width   =", N_total.bit_length(), "bits")
print("K_state (Yuga Step, Vipalas/state) =", K_state, "=", K_state//(31_557_600*1000//16), "yr/state")
print("Yuga Step hex (64b) = 0x%016X" % K_state)
print("N_total   hex (64b) = 0x%016X" % N_total)

# NCO per-clock increment to advance the Vipala counter in real time
# inc = (Vipalas/sec)/f_clk = (1/0.016)/f_clk , fixed-point with F frac bits
from math import log2, ceil
vps = Fraction(1000,16)                                  # 62.5 Vipalas/sec
total_clocks = T_MY_s_i * F_CLK
F_req = ceil(log2(total_clocks))                         # frac bits to hold <1 Vipala over a Mahayuga
print("\ntotal clocks / Mahayuga =", total_clocks, "(~2^%.1f)" % log2(total_clocks))
print("frac bits F to keep <1 Vipala over full Mahayuga =", F_req)
for F in (40, 64, F_req):
    inc = round(Fraction(vps, F_CLK) * (1 << F))
    print("  F=%-3d  K_inc = 0x%X  (%d-bit)" % (F, inc, inc.bit_length()))

# 108-entry boundary LUT: entry[i] = cumulative Vipalas at start of state i
lut = [i * K_state for i in range(STATES)]
print("\nfirst/last entries: [0]=0x%016X  [107]=0x%016X" % (lut[0], lut[107]))

# write .coe (Vivado BRAM init) and .mem ($readmemh)
base = r"C:\Users\Ayush\AppData\Local\Temp\claude\c--Users-Ayush-Desktop-Project-ansh\62155f2d-eae5-412d-a020-c8496acc14ad\scratchpad"
with open(base + r"\yuga_lut.coe", "w") as f:
    f.write("; Ansh-108 Yuga Mapping BRAM init -- 108 x 64-bit Vipala boundaries\n")
    f.write("memory_initialization_radix=16;\n")
    f.write("memory_initialization_vector=\n")
    f.write(",\n".join("%016X" % v for v in lut) + ";\n")
with open(base + r"\yuga_lut.mem", "w") as f:
    f.write("\n".join("%016X" % v for v in lut) + "\n")
print("wrote yuga_lut.coe and yuga_lut.mem")

# print full table for the chat
print("\n--- FULL 108-ENTRY HEX TABLE (state : cum_Vipalas) ---")
for i in range(STATES):
    print("%3d %016X" % (i, lut[i]))
