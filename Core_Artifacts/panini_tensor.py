# Can a Panini sandhi rule be a linear/affine map over Z/108Z?
# Principled, fixed-in-advance feature codes (NOT fit to the answers).
#
# Features (standard articulatory classification):
#   place : guttural=0, palatal=1, labial=2, retroflex=3   (4 values -> fits 2^2=4)
#   grade : zero=0, guna=1, vrddhi=2                        (base-3  -> fits 3^3=27)
#   length: short=0, long=1
# e,o = guna grade (inherently long); ai,au = vrddhi grade (long).

vows = {
    'a':(0,0,0), 'aa':(0,0,1),
    'i':(1,0,0), 'ii':(1,0,1),
    'u':(2,0,0), 'uu':(2,0,1),
    'r':(3,0,0), 'rr':(3,0,1),
    'e':(1,1,1), 'o':(2,1,1),
    'ai':(1,2,1), 'au':(2,2,1),
}
feat2name = {f: n for n, f in vows.items()}

def code(v):                       # CRT pack using the SAME idempotents as the proof file
    p, g, l = vows[v]
    m4, m27 = p, (g + 3 * l)       # place -> mod-4 track ; grade/length -> mod-27 track
    return (81 * m4 + 28 * m27) % 108

# ---- Ground-truth sandhi tables (canonical Sanskrit grammar) ----
guna   = {('a','i'):'e', ('a','ii'):'e', ('aa','i'):'e', ('aa','ii'):'e',
          ('a','u'):'o', ('a','uu'):'o', ('aa','u'):'o', ('aa','uu'):'o'}      # 6.1.87
vrddhi = {('a','e'):'ai', ('a','ai'):'ai', ('aa','e'):'ai', ('aa','ai'):'ai',
          ('a','o'):'au', ('a','au'):'au', ('aa','o'):'au', ('aa','au'):'au'}  # 6.1.88
savarna = {}                                                                   # 6.1.101
for base in ['a','i','u','r']:
    s, lng = base, base + base[-1] if False else None
for (s, L) in [('a','aa'),('i','ii'),('u','uu'),('r','rr')]:
    for x in (s, L):
        for y in (s, L):
            savarna[(x, y)] = L   # homogeneous vowels -> long version

# ============ TEST A: is guna+vrddhi the affine law "grade := R.grade+1"? ============
def predict_increment(L, R):
    pr, gr, lr = vows[R]
    out = (pr, min(gr + 1, 2), 1)         # place copied, grade+1 (capped), length:=long
    return feat2name.get(out)
gv = {**guna, **vrddhi}
hits = sum(predict_increment(L, R) == out for (L, R), out in gv.items())
print("TEST A  guna+vrddhi via 'grade:=R.grade+1':  %d/%d exact" % (hits, len(gv)))

# ============ TEST B: does ONE global affine map over Z/108Z fit ALL sandhi? ============
all_rules = {**guna, **vrddhi, **savarna}
triples = [(code(L), code(R), code(out)) for (L, R), out in all_rules.items()]
best = (-1, None)
for a in range(108):
    for b in range(108):
        for g in range(108):
            ok = sum(1 for L, R, O in triples if (a*L + b*R + g) % 108 == O)
            if ok > best[0]:
                best = (ok, (a, b, g))
print("TEST B  best single affine a*L+b*R+g (mod108): %d/%d  coeffs=%s"
      % (best[0], len(triples), best[1]))

# ============ TEST C: why it fails -- same left 'a', output depends on R's class ====
print("TEST C  same left vowel 'a', different rule fires by relation to R:")
for R in ['a', 'i', 'e']:
    rule = ('savarna' if (vows['a'][0] == vows[R][0]) else
            'vrddhi' if vows[R][1] >= 1 else 'guna')
    out = all_rules.get(('a', R))
    print("   a + %-2s -> %-3s   (%s; selected by checking R.place==a.place? and R.grade)"
          % (R, out, rule))

# CRT-track view of the increment law
print("CRT view: place(4)=exactly the mod-4 track; grade=base-3 digit in the mod-27 track.")
print("   but place gains a 5th value (vocalic l) -> 5 does NOT divide 108 (breaks mod-4 fit);")
print("   and grade '+1' must be CAPPED at 2 and length forced to 1 -> non-linear residue.")
