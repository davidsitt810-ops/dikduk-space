"""Per opportunity: of the page's X vowels after letter c (clean takes, correct reader), the share noted X->Y (false);
on a planted exam, of the planted X vowels after c, the share told. usage: perletter.py X Y correct=... planted=..."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU
from nikud import parse_verse
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
X, Y = sys.argv[1], sys.argv[2]; args = dict(a.split('=', 1) for a in sys.argv[3:])
def tally(name, planted):
    opp = collections.Counter(); hit = collections.Counter()
    for r in RU.load(V, name):
        if not r['clean']: continue
        pv = parse_verse(r['raw']['nikud']); P = set(r.get('planted') or [])
        if len(pv) != len(r['words']): continue
        N = RU.notes(r, furtive=True)
        orig = parse_verse(r['raw']['nikud']) if not planted else None
        for i, (_, L, us) in enumerate(pv):
            if planted and i not in P: continue
            if not planted and i in P: continue
            if r['marks'][i] == 'off': continue
            got = {d['k'] for d in N.get(i, []) if d['ref'] == X and d['you'] == Y}
            for u in us:
                if u['kind'] != 'vowel' or u['c'] != X: continue
                c = L[u['k']] if u['k'] < len(L) else '?'
                opp[c] += 1; hit[c] += any(abs(k - u['k']) <= 1 for k in got) if planted else (u['k'] in got)
    return opp, hit
oc, hc = tally(args['correct'], False)
op, hp = tally(args['planted'], True) if 'planted' in args else (collections.Counter(), collections.Counter())
print(f'{X}->{Y}: after letter | correct reader: false share (of page-{X}) | planted: told share')
tot_o, tot_h = sum(oc.values()), sum(hc.values())
print(f'   all   {hc and tot_h:4d}/{tot_o:5d} = {100*tot_h/max(1,tot_o):4.1f}%   |  {sum(hp.values()):4d}/{sum(op.values()):4d} = {100*sum(hp.values())/max(1,sum(op.values())):4.1f}%')
for c, n in oc.most_common():
    if n < 40: continue
    print(f'   {c}     {hc[c]:4d}/{n:5d} = {100*hc[c]/n:4.1f}%   |  {hp[c]:4d}/{op[c]:4d} = {100*hp[c]/max(1,op[c]):4.1f}%')
