"""One kind of vowel note (e.g. E->I: the page says eh, the ear heard ee) on a correct reader (every such note false)
against the same reader with the page rewritten so that exactly this note is the right one (PLANT=IE for E->I: every
planted word a real ee where the page says eh). How the two look (the ear's own numbers per slot), and candidate rules
that drop a note of this kind: false words removed against planted words lost.
usage: sweep.py KIND correct=<name>[+...] planted=<name>[+...] [perakim=a-b]      (KIND like E->I)"""
import sys, os, json, collections
import numpy as np
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); R = '/home/claude/dikduk-space'
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tools'))
import false_notes as FN

KIND = sys.argv[1]; REF, YOU = KIND.split('->')
args = dict(a.split('=', 1) for a in sys.argv[2:])
lo, hi = (int(x) for x in args.get('perakim', '1-150').split('-'))
def load(spec):
    rows = []
    for nm in spec.split('+'):
        rows += [r for r in json.load(open(os.path.join(V, f'exam_{nm}.json'), encoding='utf-8')) if 'raw' in r and 'words' in r and lo <= r['per'] <= hi]
    return rows
C, P = load(args['correct']), load(args['planted'])

def slot(r, n):
    for s in r['raw']['tw'][n['w']]:
        if s[1] == n['you'] and abs((s[3] or 0) - (n['p'] or 0)) < 1e-9: return s
    return None
def feats(r, n):
    s = slot(r, n); m = s[2] if s else {}; tot = sum(m.values()) or 1e-9
    return {'ref_share': m.get(REF, 0) / tot, 'you_share': m.get(YOU, 0) / tot, 'you_mass': m.get(YOU, 0), 'tot': tot,
            'p': n['p'] or 0, 'place': n['place'], 'after': n['after'], 'next': n['next'], 'src': n['src'],
            'second': max((v / tot for k, v in m.items() if k != YOU), default=0), 'nslots': len(r['raw']['tw'][n['w']])}
def notes(rows, planted):
    """-> per row: (row, P, [(note, feats)]) with all its notes (any kind) on words shown"""
    out = []
    for r in rows:
        Pw = set(r.get('planted') or []) if planted else set()
        ns = FN.notes_detail(r)
        out.append((r, Pw, [(n, feats(r, n) if (n['ref'], n['you']) == (REF, YOU) else None) for n in ns]))
    return out
NC, NP = notes(C, False), notes(P, True)

def score(keep):
    """keep(f) -> True to keep a note of KIND. -> (false words on the correct reader, planted words told, planted words)"""
    fw = 0
    for r, _, ns in NC:
        fw += len({n['w'] for n, f in ns if f is None or keep(f)})
    told = pw = 0
    for r, Pw, ns in NP:
        W = {n['w'] for n, f in ns if f is None or keep(f)}
        pw += len(Pw); told += sum(1 for i in Pw if i in W or r['marks'][i] == 'off')
    return fw, told, pw

if __name__ == '__main__':
    words_c = sum(len(r['words']) for r in C)
    falseK = [f for _, _, ns in NC for n, f in ns if f is not None]
    trueK = [f for _, Pw, ns in NP for n, f in ns if f is not None and n['w'] in Pw]
    print(f'{KIND}: correct {len(C)} takes ({words_c} words), {len(falseK)} {KIND} notes (all false) | planted {len(P)} takes, {len(trueK)} {KIND} notes on planted words (right ones)')
    q = lambda a: ' '.join(f'{x:.3f}' for x in np.percentile(a, [10, 25, 50, 75, 90])) if a else '-'
    for k in ('ref_share', 'you_share', 'second', 'you_mass', 'tot', 'p', 'nslots'):
        print(f'   {k:10s} false p10..p90 {q([f[k] for f in falseK])}   | right {q([f[k] for f in trueK])}')
    for k in ('place', 'src', 'after', 'next'):
        cf, ct = collections.Counter(f[k] for f in falseK), collections.Counter(f[k] for f in trueK)
        keys = [x for x, _ in (cf + ct).most_common(12)]
        print(f'   {k:6s} ' + '  '.join(f'{x}: {cf[x]}/{ct[x]}' for x in keys) + '   (false/right)')
    base = score(lambda f: True)
    print(f'\nnow: false words {base[0]} ({100 * base[0] / words_c:.2f}% of {words_c}), planted told {base[1]}/{base[2]} ({100 * base[1] / max(1, base[2]):.1f}%)')
    rules = [('drop all ' + KIND, lambda f: False)]
    for x in (0.01, 0.02, 0.05, 0.1): rules.append((f'keep if ref_share <= {x}', lambda f, x=x: f['ref_share'] <= x))
    for x in (0.9, 0.95, 0.99): rules.append((f'keep if p >= {x}', lambda f, x=x: f['p'] >= x))
    for x in (0.5, 1.0, 2.0, 3.0): rules.append((f'keep if you_mass >= {x}', lambda f, x=x: f['you_mass'] >= x))
    for label, keep in rules:
        fw, t, pw = score(keep)
        print(f'   {label:28s} false words {fw:4d} ({100 * fw / words_c:.2f}%), planted told {t}/{pw} ({100 * t / max(1, pw):.1f}%)')
