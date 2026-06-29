# Deep asiddha chain stress test: where does host scheduling starve the 108-chip?
#
# asiddhatva (8.2.1 purvatrasiddham): tripadi rules apply in STRICT textual order;
# each rule's trigger is created by the previous rule's OUTPUT. Two consequences:
#   (1) no reordering (serial), and
#   (2) the host cannot schedule step k+1 until the chip finishes step k
#       (data dependency) -> host and chip CANNOT pipeline/overlap.
# So chain latency = sum over steps of (host_select + chip_execute).

import sys
sys.stdout.reconfigure(encoding="utf-8")

# ---- a representative depth-5 serial chain (each step's trigger = prev output) ----
# Abstract but faithful: state is a token; each rule fires only on the prior result.
def r1(s): return s + "|jastva"     # 8.2.39  voicing
def r2(s): return s + "|nalopa"     # 8.2.7   n-deletion (created by r1's output)
def r3(s): return s + "|scutva"     # 8.4.40  palatalization (needs r2's output)
def r4(s): return s + "|stutva"     # 8.4.41  retroflexion (needs r3's output)
def r5(s): return s + "|parasav"    # 8.4.58  homorganic nasal (needs r4's output)
CHAIN = [r1, r2, r3, r4, r5]
DEPTH = len(CHAIN)

# ---- transparent cost model (cycles; 1 GHz -> 1 cycle = 1 ns) ----
E_chip   = 10      # chip cycles per transform (one CRT recombine + residue ops)
c_check  = 5       # host cycles to test ONE rule's domain predicate
S_index  = 20      # host cycles to select next rule when INDEXED (tripadi pointer)
clock_GHz = 1.0
budget_ms = 10.0   # real-time budget per junction (a generous syllable window)

def host_cost(mode, N):
    return S_index if mode == "indexed" else N * c_check   # scan = O(N)

def run_chain(mode, N):
    """Simulate the serial chain; count host checks and chip transforms."""
    state, host_cycles, chip_cycles = "ROOT", 0, 0
    for rule in CHAIN:               # strict order, no reordering (asiddha)
        host_cycles += host_cost(mode, N)   # host selects/sequences this step
        state = rule(state)                 # chip executes the transform
        chip_cycles += E_chip
    total = host_cycles + chip_cycles       # NO overlap (data dependency)
    util = chip_cycles / total              # fraction of time chip is doing work
    return host_cycles, chip_cycles, total, util

print("=== Depth-%d asiddha chain ===" % DEPTH)
for mode, N in [("indexed", None), ("scan", 200), ("scan", 4000)]:
    Nn = N if N else 1
    h, c, t, u = run_chain(mode, Nn)
    tag = mode + ("" if mode == "indexed" else " N=%d" % N)
    print("  %-12s host=%7d ns  chip=%4d ns  total=%8d ns  chip-util=%6.2f%%"
          % (tag, h, c, t, 100*u))

# ---- the crossover: host overhead == chip execution (util = 50%) ----
S_idx = host_cost("indexed", 1)
print("\n=== Crossover (host time per step == chip time per step) ===")
print("  Chip transform   E = %d ns/step" % E_chip)
print("  Indexed select   S = %d ns/step  -> S>E? %s  (chip util = %.1f%%)"
      % (S_idx, S_idx > E_chip, 100*E_chip/(S_idx+E_chip)))
N_star = E_chip / c_check
print("  SCAN crossover: host==chip when N* = E/c_check = %.1f rules scanned/step"
      % N_star)
print("  => if the host weighs more than %.0f candidate rules per step, it is the bottleneck"
      % N_star)

# ---- utilization is CONSTANT in depth; only absolute latency scales ----
print("\n=== Depth sweep (indexed): util is flat, latency is linear ===")
for D in [1, 2, 5, 7, 10, 100]:
    per = S_idx + E_chip
    print("  D=%-4d latency=%6d ns  chip-util=%5.2f%%  asiddha-tax=(D-1)*S=%5d ns"
          % (D, D*per, 100*E_chip/per, (D-1)*S_idx))

# ---- depth ceiling: how deep before we blow the real-time budget? ----
budget_ns = budget_ms * 1e6
print("\n=== Depth ceiling vs %.0f ms budget ===" % budget_ms)
for mode, N in [("indexed", 1), ("scan", 200), ("scan", 4000)]:
    per = host_cost(mode, N) + E_chip
    Dmax = int(budget_ns // per)
    tag = mode if mode == "indexed" else "scan N=%d" % N
    print("  %-12s per-step=%8d ns  ->  D_max = %d steps" % (tag, per, Dmax))
print("\n(real asiddha chains are depth ~2-7; compare to the D_max above)")
