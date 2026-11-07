"""The word rule's drop bar, replayed from an exam's raw rule inputs (RAW=1 rows with raw.rule_in, tools/exam_voice.py).
For a skipped-word exam (PLANT=SKIP): the skipped word red (told), "not sure", or passed; the other words red.
For a correct reader: the words red (all false).
usage: drops.py <variant> <exam name>[+<name>...] ...
  variant: comma-separated drop=<nats>, margin=<nats>, hskel=<.8>, hkept=<.6>, or "-" for the live rule"""
import sys, os, json, math
sys.path.insert(0, '/home/claude/dikduk-space')
import numpy as np
import rule
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0, c - h), 100 * min(1, c + h))
def pct(k, n): lo, hi = wilson(k, n); return f'{k}/{n} = {100 * k / max(1, n):.1f}% ({lo:.1f}–{hi:.1f})'

import inspect
_SRC = inspect.getsource(rule.marks_of)
_LIVE = "heard = (TW[top].get('skel') or 0) >= .8 and (TW[top].get('kept') or 0) >= .6"
assert _SRC.count(_LIVE) == 1
_CACHE = {}
def marks_of(hskel, hkept):
    """rule.marks_of with the "heard" guard's two bars as parameters (the live function's own source, one line changed)"""
    if (hskel, hkept) not in _CACHE:
        ns = dict(rule.__dict__); ns['HS'] = hskel; ns['HK'] = hkept
        exec(_SRC.replace(_LIVE, "heard = (TW[top].get('skel') or 0) >= HS and (TW[top].get('kept') or 0) >= HK"), ns)
        _CACHE[(hskel, hkept)] = ns['marks_of']
    return _CACHE[(hskel, hkept)]

def marks(r, drop=None, margin=None, hskel=.8, hkept=.6):
    """the page's marks for the row, from its stored rule inputs, with the drop bar / margin / "heard" guard changed"""
    ri = r['raw']['rule_in']; TW = ri['tw']; F = [({'fit': x} if x is not None else None) for x in ri['fit']] or None
    old = dict(rule.RULE)
    try:
        if drop is not None: rule.RULE['drop'] = drop
        if margin is not None: rule.RULE['margin'] = margin
        m, why, lw, ch = marks_of(hskel, hkept)(TW, F, r['gap'], rule.clean_of(TW), r['rival'])
    finally: rule.RULE.clear(); rule.RULE.update(old)
    if r.get('no_speech'): m = ['unsure' if x else x for x in m]
    return m

def parse(v):
    kw = {}
    for part in ([] if v == '-' else v.split(',')):
        k, _, x = part.partition('='); kw[k] = float(x)
    return kw

if __name__ == '__main__':
    kw = parse(sys.argv[1])
    for spec in sys.argv[2:]:
        rows = []
        for nm in spec.split('+'):
            p = os.path.join(V, f'exam_{nm}.json')
            if os.path.exists(p): rows += [r for r in json.load(open(p, encoding='utf-8')) if 'raw' in r and 'rule_in' in r['raw']]
        if not rows: print(f'{spec}: no rows'); continue
        diff = sum(1 for r in rows if marks(r) != r['marks'])
        skip = any(r.get('skip_t') for r in rows)
        if skip:
            rows = [r for r in rows if r.get('skip_ok')]
            t = u = ps = oth = ow = 0
            for r in rows:
                m = marks(r, **kw); j = r['planted'][0]
                t += m[j] == 'off'; u += m[j] == 'unsure'; ps += m[j] == 'ok'
                oth += sum(1 for i, x in enumerate(m) if x == 'off' and i != j); ow += len(m) - 1
            n = len(rows)
            print(f'{spec}: {n} takes (live replay differs on {diff}); skipped word red {pct(t, n)}, not sure {u}, passed {ps}; other words red {pct(oth, ow)}')
        else:
            off = sum(1 for r in rows for x in marks(r, **kw) if x == 'off'); W = sum(len(r['marks']) for r in rows)
            print(f'{spec}: {len(rows)} takes (live replay differs on {diff}); words red {off} of {W}')
