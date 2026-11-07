"""Two exams of the same takes under different heads (e.g. the shipped head against a calibrated one), each replayed
with the same rule (v5.6 by default: the furtive patah), paired by take (perek, pasuk).
Correct readers: words with a vowel note, words red. Planted: planted words told; other words noted.
usage: headcmp.py <base exam>[:a-b] <new exam> [variant]     (variant as in compare.py; default "furtive")"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C, rules as RU
V = C.V
a_spec, b_name = sys.argv[1], sys.argv[2]; kw = C.parse(sys.argv[3] if len(sys.argv) > 3 else 'furtive')
a_name, _, rng = a_spec.partition(':'); lo, hi = (int(x) for x in (rng or '1-150').split('-'))
A = {(r['per'], r['ps']): r for r in RU.load(V, a_name, lo, hi)}; B = {(r['per'], r['ps']): r for r in RU.load(V, b_name, lo, hi)}
keys = sorted(set(A) & set(B))
print(f'{a_spec} vs {b_name}: {len(keys)} takes in common ({len(A)} / {len(B)}); clean {sum(A[k]["clean"] for k in keys)} / {sum(B[k]["clean"] for k in keys)}')
planted = any(A[k].get('planted') is not None for k in keys)
tot = {'a': [0, 0, 0, 0, 0], 'b': [0, 0, 0, 0, 0]}; only_a = only_b = 0
for k in keys:
    ra, rb = A[k], B[k]
    if len(ra['words']) != len(rb['words']): continue
    P = set(ra.get('planted') or [])
    ga, gb = RU.noted(ra, **kw), RU.noted(rb, **kw)
    for nm, r, g in (('a', ra, ga), ('b', rb, gb)):
        t = tot[nm]
        t[0] += sum(1 for i in P if i in g or r['marks'][i] == 'off'); t[1] += len(P)
        t[2] += len(g - P); t[3] += len(r['words']) - len(P); t[4] += sum(1 for i, m in enumerate(r['marks']) if m == 'off' and i not in P)
    if planted:
        for i in P:
            ta = i in ga or ra['marks'][i] == 'off'; tb = i in gb or rb['marks'][i] == 'off'
            only_a += ta and not tb; only_b += tb and not ta
    else:
        only_a += len((ga - gb) - P); only_b += len((gb - ga) - P)
a, b = tot['a'], tot['b']
if planted:
    print(f'   planted told {C.pct(a[0], a[1])} -> {C.pct(b[0], b[1])}   (told only by the base {only_a}, only by the new {only_b})')
    print(f'   other words noted {C.pct(a[2], a[3])} -> {C.pct(b[2], b[3])}')
else:
    print(f'   words with a vowel note {C.pct(a[2], a[3])} -> {C.pct(b[2], b[3])}   (noted only under the base {only_a}, only under the new {only_b})')
print(f'   words red {a[4]} -> {b[4]}')
