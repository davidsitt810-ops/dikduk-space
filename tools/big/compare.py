"""A rule variant against the server's v5.5, replayed on the same takes of each exam (raw slots, RAW=1).
Correct readers: words with a vowel note (all false). Planted exams: planted words told (all takes, clean takes),
other words noted.
usage: compare.py <variant> <exam name>[:a-b] ...
  variant: comma-separated parts —
    furtive | furtive2           a furtive patah expected where it is said (furtive2: and optional)
    ei=<x>                       the v5.5 e-for-i guard's share (0.005 live)
    cal=<theta>/<min>/<EI|all>[/w]   per-take calibration (w: only the take's other words count)
    unst=<XY>[+<XY>...]          drop page-X heard-Y notes on unstressed vowels (e.g. unst=AE+IE)
    unstc=<XY>[+<XY>...]         ... only on unstressed vowels in a closed syllable
    throat=<XY>[+<XY>...]        drop page-X heard-Y notes on a vowel right after ע / ח
    drop=<XY>[+<XY>...]          drop page-X heard-Y notes everywhere
  "-" alone: v5.5 (prints the baseline)"""
import sys, os, math
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(V, 'big'))
import rules as RU
VW = 'AEIOU'
def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))
def pct(k, n): lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'
def pairs(s): return tuple((p[0], p[1]) for p in s.split('+'))

def parse(v):
    kw, hooks = {}, []
    for part in ([] if v == '-' else v.split(',')):
        if part == 'furtive': kw['furtive'] = True
        elif part == 'furtive2': kw['furtive'] = 2
        elif part.startswith('ei='): kw['ei'] = float(part[3:])
        elif part.startswith('cal='):
            a = part[4:].split('/')
            K = (('E', 'I'),) if a[2] == 'EI' else tuple((x, y) for x in VW for y in VW if x != y) if a[2] == 'all' else pairs(a[2])
            hooks.append(RU.calibrated(float(a[0]), int(a[1]), K, same_word=not (len(a) > 3 and a[3] == 'w')))
        elif part.startswith('unst='): hooks.append(RU.unstressed(pairs(part[5:])))
        elif part.startswith('unstc='): hooks.append(RU.unstressed(pairs(part[6:]), closed_only=True))
        elif part.startswith('throat='): hooks.append(RU.after_letters(pairs(part[7:])))
        elif part.startswith('drop='):
            D = set(pairs(part[5:])); hooks.append(lambda st, rs, L, i, ctx, D=D: (rs['heard'], st['heard']) not in D)
        else: raise SystemExit(f'unknown variant part {part!r}')
    h = RU.both(*hooks)
    if h is not None: kw['keep'] = h
    return kw

def count(rows, **args):
    told = pw = oth = ow = told_c = pw_c = 0
    for r in rows:
        P = set(r.get('planted') or []); got = RU.noted(r, **args)
        t = sum(1 for i in P if i in got or r['marks'][i] == 'off')
        pw += len(P); told += t; oth += len(got - P); ow += len(r['words']) - len(P)
        if r['clean']: pw_c += len(P); told_c += t
    return told, pw, oth, ow, told_c, pw_c

if __name__ == '__main__':
    kw = parse(sys.argv[1])
    for spec in sys.argv[2:]:
        nm, _, rng = spec.partition(':'); lo, hi = (int(x) for x in (rng or '1-150').split('-'))
        rows = RU.load(V, nm, lo, hi)
        if not rows: print(f'{spec}: no rows'); continue
        planted = any(r.get('planted') is not None for r in rows)
        o = count(rows); n = count(rows, **kw) if kw else o
        if planted:
            print(f'{spec:22s} planted told {pct(o[0], o[1])} -> {pct(n[0], n[1])}')
            print(f'{"":22s}   on clean takes {pct(o[4], o[5])} -> {pct(n[4], n[5])}')
            print(f'{"":22s}   other words noted {pct(o[2], o[3])} -> {pct(n[2], n[3])}')
        else: print(f'{spec:22s} words noted {pct(o[2], o[3])} -> {pct(n[2], n[3])}')
