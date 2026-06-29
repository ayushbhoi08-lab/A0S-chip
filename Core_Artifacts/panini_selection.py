# How much "weight" does the brain (rule-selection) carry vs the muscle (transform)?
# Build the real Panini vowel-sandhi SELECTION function over every junction and
# measure how much of it is irreducibly relational (compare BOTH operands) vs
# factorable into cheap unary lookups.

from math import log2
from collections import Counter, defaultdict

aclass  = ['a', 'aa']                          # a-class
ikclass = ['i', 'ii', 'u', 'uu', 'r', 'rr']    # ik (simple, non-a)
ecclass = ['e', 'o', 'ai', 'au']               # ec (compound)
vowels  = aclass + ikclass + ecclass
simple  = set(aclass + ikclass)                # savarna-eligible
place   = {'a':0,'aa':0, 'i':1,'ii':1, 'u':2,'uu':2, 'r':3,'rr':3,
           'e':1,'ai':1, 'o':2,'au':2}
def cls(v): return 'a' if v in aclass else ('ik' if v in ikclass else 'ec')

# ---- the real selection function (minimal predicate form) ----
def rule(L, R):
    if L in simple and R in simple and place[L] == place[R]:
        return 'savarna'                                  # 6.1.101  (RELATIONAL)
    if L in aclass:
        return 'vrddhi' if R in ecclass else 'guna'       # 6.1.88 / 6.1.87 (unary on R)
    if L in ikclass:
        return 'yan'                                      # 6.1.77   (unary on L)
    return 'ayadi'                                        # 6.1.78   (unary on L)

pairs = [(L, R) for L in vowels for R in vowels]
N = len(pairs)
dist = Counter(rule(L, R) for L, R in pairs)
H = -sum((c/N) * log2(c/N) for c in dist.values())
print("Junctions:", N, " rule distribution:", dict(dist))
print("Rule-choice entropy: %.3f bits (floor for %d rules = %.3f)"
      % (H, len(dist), log2(len(dist))))

# ---- Factorability: is rule(L,R) determined by (class L, class R) ALONE? ----
cell_rules = defaultdict(set)
for L, R in pairs:
    cell_rules[(cls(L), cls(R))].add(rule(L, R))
mixed = {c: rs for c, rs in cell_rules.items() if len(rs) > 1}
relational_pairs = [(L, R) for L, R in pairs if (cls(L), cls(R)) in mixed]
print("\n3x3 class-routing table (pure cells = unary-decidable):")
for cl in ['a','ik','ec']:
    print("  L=%-3s" % cl,
          {cr: (list(cell_rules[(cl,cr)])[0] if len(cell_rules[(cl,cr)])==1
                else 'MIXED'+str(sorted(cell_rules[(cl,cr)]))) for cr in ['a','ik','ec']})
print("Mixed (irreducibly relational) class-cells:", list(mixed.keys()))
print("Junctions needing a genuine L-R comparison: %d / %d = %.0f%%"
      % (len(relational_pairs), N, 100*len(relational_pairs)/N))

# ---- Does ONE extra predicate (place equality) resolve every mixed cell? ----
def rule_factored(L, R):
    c = (cls(L), cls(R))
    if c in mixed:                                   # consult the single relational predicate
        return 'savarna' if place[L] == place[R] else 'yan'
    return list(cell_rules[c])[0]                    # else pure unary cell
mismatch = sum(rule_factored(L, R) != rule(L, R) for L, R in pairs)
print("\nFactored model (3x3 table + 1 equality predicate) mismatches:", mismatch, "/", N)

# ---- Brain cost per junction: unary lookups vs relational comparisons ----
unary = N * 1                       # class(L) always; class(R) only in a-branch -> count conservatively
rel   = len(relational_pairs)       # relational comparisons actually evaluated
print("Avg relational comparisons (the irreducible IF) per junction: %.3f"
      % (rel / N))
print("Compression: %d-entry selection table  ->  9-cell routing table + 1 comparator"
      % N)
