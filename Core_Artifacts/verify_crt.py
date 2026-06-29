from math import gcd

# 1. CRT bijection: x -> (x mod 4, x mod 27) on 0..107
pairs = {}
for x in range(108):
    pairs[(x % 4, x % 27)] = x
print("distinct residue pairs:", len(pairs), "(want 108)")

# 2. Reconstruction idempotents and formula x = 81a + 28b (mod 108)
print("81 ->", 81 % 4, 81 % 27, "(want 1,0)")
print("28 ->", 28 % 4, 28 % 27, "(want 0,1)")
bad = [x for x in range(108) if (81 * (x % 4) + 28 * (x % 27)) % 108 != x]
print("reconstruction failures:", bad, "(want [])")

# 3. Independent parallel multiply, branch-free recombine, vs direct
def mul_tracks(x, y):
    a = (x % 4) * (y % 4) % 4          # track A only
    b = (x % 27) * (y % 27) % 27       # track B only
    return (81 * a + 28 * b) % 108     # fixed linear recombine
mism = [(x, y) for x in range(108) for y in range(108)
        if mul_tracks(x, y) != (x * y) % 108]
print("parallel-multiply mismatches over all 108x108:", len(mism))
print("worked: 50*7 via tracks =", mul_tracks(50, 7), " direct =", (50 * 7) % 108)

# 4. Units mod 108 -> division is only defined for units
units = [x for x in range(108) if gcd(x, 108) == 1]
print("phi(108) units:", len(units), " non-units:", 108 - len(units))
print("gcd(50,108) =", gcd(50, 108), "-> 50 not invertible")

# 5. Residue pairs not order-monotonic -> comparison needs reconstruction
print("23 ->", (23 % 4, 23 % 27), "  50 ->", (50 % 4, 50 % 27),
      " : 23<50 yet first coord 3 > 2")
