"""The same takes under the old note rule, offline: v5.4 (no "ee where the page says eh" filter: EI_MAX_E = 1) against
v5.5 (the server's, EI_MAX_E = 0.005), from the raw slots the exams kept (RAW=1). First a check that replaying v5.5
gives exactly the notes the server itself gave on every take; a replay that disagrees with the server is not trusted.
usage: replay.py <label>=<name>[+<name>...] ..."""
import sys, os, json, math
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); R = '/home/claude/dikduk-space'
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tools'))
import vowels, false_notes as FN

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))
def pct(k, n): lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'

def server_noted(r):
    if not r['clean']: return set()
    out = set()
    for src in ('sv', 'svn'):
        for i, ds in ((r['raw'].get(src) or {}).items()):
            if ds and r['marks'][int(i)] != 'off': out.add(int(i))
    return out

def noted(r, ei):
    vowels.EI_MAX_E = ei
    return {n['w'] for n in FN.notes_detail(r)}

for spec in sys.argv[1:]:
    label, names = spec.split('=', 1); rows = []
    for nm in names.split('+'):
        p = os.path.join(V, f'exam_{nm}.json')
        if os.path.exists(p): rows += [r for r in json.load(open(p, encoding='utf-8')) if 'raw' in r and 'words' in r]
    if not rows: print(f'\n== {label}: no rows'); continue
    planted = any(r.get('planted') is not None for r in rows)
    bad = 0; c = {k: [0, 0, 0, 0] for k in ('v5.4', 'v5.5')}   # [planted told, planted words, other noted, other words]
    for r in rows:
        P = set(r.get('planted') or []); W = len(r['words'])
        new = noted(r, 0.005); bad += new != server_noted(r)
        for k, ei in (('v5.4', 1.0), ('v5.5', 0.005)):
            got = new if k == 'v5.5' else noted(r, ei)
            c[k][0] += sum(1 for i in P if i in got or r['marks'][i] == 'off'); c[k][1] += len(P)
            c[k][2] += len(got - P); c[k][3] += W - len(P)
    vowels.EI_MAX_E = 0.005
    print(f'\n== {label}: {len(rows)} takes; the replay of v5.5 differs from the server on {bad} takes')
    for k in ('v5.4', 'v5.5'):
        t, pw, o, ow = c[k]
        print(f'   {k}: ' + (f'planted words told {pct(t, pw)}; other words noted {pct(o, ow)}' if planted else f'words with a vowel note {pct(o, ow)}'))
