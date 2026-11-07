"""The per-take calibration rule against the server's v5.5, replayed on the same takes (raw slots, RAW=1).
A note "you said Y where the page says X" is dropped when, among the take's other page-X vowels (at least min_n),
a share >= theta was heard as Y too.
usage: calib.py <theta> <min_n> <EI|all> <furtive 0|1> <exam name>[:a-b] ...
Correct readers: words with a vowel note (all false). Planted exams: planted words told (all takes and clean takes),
other words noted."""
import sys, os, math
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(V, 'big'))
import rules as RU

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))
def pct(k, n): lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'

VW = 'AEIOU'
if __name__ == '__main__':
    theta, min_n, kinds, fur = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3], bool(int(sys.argv[4]))
    K = (('E', 'I'),) if kinds == 'EI' else tuple((a, b) for a in VW for b in VW if a != b)
    keep = RU.calibrated(theta, min_n, K)
    for spec in sys.argv[5:]:
        nm, _, rng = spec.partition(':'); lo, hi = (int(x) for x in (rng or '1-150').split('-'))
        rows = RU.load(V, nm, lo, hi)
        if not rows: print(f'{spec}: no rows'); continue
        planted = any(r.get('planted') is not None for r in rows)
        c = {}
        for k, args in (('v5.5', {}), ('new', {'furtive': fur, 'keep': keep})):
            told = pw = oth = ow = told_c = pw_c = 0
            for r in rows:
                P = set(r.get('planted') or []); got = RU.noted(r, **args)
                t = sum(1 for i in P if i in got or r['marks'][i] == 'off')
                pw += len(P); told += t; oth += len(got - P); ow += len(r['words']) - len(P)
                if r['clean']: pw_c += len(P); told_c += t
            c[k] = (told, pw, oth, ow, told_c, pw_c)
        o, n = c['v5.5'], c['new']
        if planted:
            print(f'{spec:22s} planted told {pct(o[0], o[1])} -> {pct(n[0], n[1])}')
            print(f'{"":22s}   on clean takes {pct(o[4], o[5])} -> {pct(n[4], n[5])}')
            print(f'{"":22s}   other words noted {pct(o[2], o[3])} -> {pct(n[2], n[3])}')
        else: print(f'{spec:22s} words noted {pct(o[2], o[3])} -> {pct(n[2], n[3])}')
