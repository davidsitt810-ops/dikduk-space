"""The ע / ח verdicts of the same takes in two exams (paired by perek and pasuk): throat / unsure / plain, as the page
shows them (a "plain" on a take that is not clean is shown as unsure). usage: throatcmp.py <exam a> <exam b> [lo-hi]"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, drops as D
V = D.V; pct = D.pct
a_name, b_name = sys.argv[1], sys.argv[2]; lo, hi = (int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else '1-150').split('-'))
A = {(r['per'], r['ps']): r for r in RU.load(V, a_name, lo, hi)}; B = {(r['per'], r['ps']): r for r in RU.load(V, b_name, lo, hi)}
keys = sorted(set(A) & set(B)); c = collections.Counter()
for k in keys:
    for nm, r in (('a', A[k]), ('b', B[k])):
        for t in r.get('throat') or []:
            ch, v = t[0] if isinstance(t, (list, tuple)) else t.get('c'), t[2] if isinstance(t, (list, tuple)) else t.get('v')
            c[(nm, ch, v)] += 1; c[(nm, ch)] += 1
print(f'{a_name} vs {b_name}: {len(keys)} takes')
for ch in ('ע', 'ח'):
    f = lambda nm: '  '.join(f'{v} {pct(c[(nm, ch, v)], c[(nm, ch)])}' for v in ('throat', 'unsure', 'plain'))
    print(f'  {ch}: {f("a")}\n     -> {f("b")}')
