"""Context rules for one kind of vowel note, on a correct reader (every note false) and on the planted mistake that
is exactly that note. usage: sweep2.py KIND correct=<names> planted=<names> [perakim=a-b]"""
import sys, os, collections
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(V, 'big'))
import rules as RU
KIND = sys.argv[1]; REF, YOU = KIND.split('->')
args = dict(a.split('=', 1) for a in sys.argv[2:]); lo, hi = (int(x) for x in args.get('perakim', '1-150').split('-'))
C = RU.load(V, args['correct'], lo, hi); P = RU.load(V, args['planted'], lo, hi) if args.get('planted') else []
def near(k, sk): return sk is not None and abs(k - sk) <= 0 
def is_kind(st, rs): return rs['heard'] == REF and st['heard'] == YOU
def unstressed(st, rs, L, i, c): return c['stress'].get(i) is not None and st['k'] != c['stress'][i] and rs.get('k', st['k']) != c['stress'][i]
def first(st, rs, L, i, c): return st['k'] == min((u['k'] for u in c['units'][i] if u['kind'] == 'vowel'), default=-1) or st['k'] == 0
def closed(st, rs, L, i, c): return c['closed'][i].get(rs.get('k', st['k']), c['closed'][i].get(st['k'], False))
def after(ch): return lambda st, rs, L, i, c: 0 <= st['k'] < len(L) and L[st['k']] == ch
RULES = [('v5.5 (keep all)', lambda *a: False), ('drop all ' + KIND, lambda *a: True), ('unstressed', unstressed), ('first vowel', first),
         ('closed syllable', closed), ('unstressed & closed', lambda *a: unstressed(*a) and closed(*a)),
         ('after א', after('א')), ('after ו', after('ו')), ('after י', after('י')), ('first & after א', lambda *a: first(*a) and after('א')(*a))]
def run(drop):
    keep = lambda st, rs, L, i, c: not (is_kind(st, rs) and drop(st, rs, L, i, c))
    fw = W = 0
    for r in C: fw += len(RU.noted(r, keep=keep)); W += len(r['words'])
    told = pw = 0
    for r in P:
        Pw = set(r.get('planted') or []); got = RU.noted(r, keep=keep)
        pw += len(Pw); told += sum(1 for i in Pw if i in got or r['marks'][i] == 'off')
    return fw, W, told, pw
print(f'{KIND}: correct {len(C)} takes, planted {len(P)} takes (perakim {lo}-{hi})')
for label, drop in RULES:
    fw, W, t, pw = run(drop)
    print(f'   {label:22s} false words {fw:4d} ({100 * fw / max(1, W):.2f}%)' + (f'   planted told {t}/{pw} ({100 * t / max(1, pw):.1f}%)' if P else ''))
