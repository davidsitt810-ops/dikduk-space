"""Bigger tests: one report over the parts of each exam (exam_<name>.json in voices/), with 95% intervals (Wilson), from what
the server itself said (its marks, its vowel notes on clean takes, its throat verdicts) — no replay.
usage: report.py <label>=<name>[+<name>...] ..."""
import sys, os, json, math, collections
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))

def pct(k, n): lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'

def load(names):
    rows = []
    for nm in names:
        p = os.path.join(V, f'exam_{nm}.json')
        if os.path.exists(p): rows += [r for r in json.load(open(p, encoding='utf-8')) if 'words' in r]
    return rows

for spec in sys.argv[1:]:
    label, names = spec.split('=', 1); rows = load(names.split('+'))
    if not rows: print(f'\n== {label}: no rows yet'); continue
    planted = any(r.get('planted') is not None for r in rows)
    W = sum(len(r['words']) for r in rows); clean = sum(1 for r in rows if r['clean'])
    noted, kinds, told, pw, other, ow, red, right = 0, collections.Counter(), 0, 0, 0, 0, 0, 0
    told_c = pw_c = 0   # the planted words on clean takes only (vowel notes are shown only on a take heard well)
    thr = collections.Counter()
    for r in rows:
        P = set(r.get('planted') or []); notes = {}
        for src in ('sv', 'svn'):
            for i, ds in ((r.get('raw') or {}).get(src) or {}).items():
                if r['clean'] and r['marks'][int(i)] != 'off': notes.setdefault(int(i), []).extend(ds)
        for ds in notes.values():
            for d in ds: kinds[f"{d['ref']}->{d['you']}"] += 1
        if planted:
            pw += len(P); told += sum(1 for i in P if i in notes or r['marks'][i] == 'off')
            if r['clean']: pw_c += len(P); told_c += sum(1 for i in P if i in notes or r['marks'][i] == 'off')
            ow += len(r['words']) - len(P); other += len(set(notes) - P)
        else:
            noted += len(notes)
        right += sum(1 for i, m in enumerate(r['marks']) if i not in P); red += sum(1 for i, m in enumerate(r['marks']) if m == 'off' and i not in P)
        for x in r.get('throat') or []: thr[(x.get('c'), x.get('raw') or x.get('v'))] += 1
    print(f'\n== {label}: {len(rows)} takes, {clean} clean ({100 * clean / len(rows):.0f}%), {W} words')
    if planted:
        print(f'   planted words told   {pct(told, pw)}')
        print(f'   … on clean takes     {pct(told_c, pw_c)}')
        print(f'   other words noted    {pct(other, ow)}')
    else:
        print(f'   words with a vowel note (a correct reader: every one false)  {pct(noted, W)}')
    print(f'   right words marked red  {pct(red, right)}')
    print(f'   vowel-note slots by kind: {dict(kinds.most_common(6))}')
    if thr:
        for c in ('ע', 'ח'):
            n = sum(v for (cc, _), v in thr.items() if cc == c)
            if n: print(f'   {c}: ' + ', '.join(f'{v} {k} ({100 * k_ / n:.0f}%)' for (cc, v), k_ in sorted(thr.items(), key=lambda x: -x[1]) if cc == c for k in [k_]))
