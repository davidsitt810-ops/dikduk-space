"""v5.6 through its own server against the v5.6 replay of the v5.5 exam, take for take: the ear's slots must be the
same, the server's vowel notes (raw sv / svn) the replay's (furtive=True), and the page's marks the drop-bar replay's
where the v5.5 row kept its rule inputs, or else differ only where v5.5 called a word "dropped".
usage: v56check.py <v5.5 exam> <v5.6 exam>"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
a_name, b_name = sys.argv[1], sys.argv[2]
A = {(r['per'], r['ps']): r for r in RU.load(V, a_name)}; B = {(r['per'], r['ps']): r for r in RU.load(V, b_name)}
keys = sorted(set(A) & set(B)); c = collections.Counter(); ex = []
for k in keys:
    a, b = A[k], B[k]
    c['takes'] += 1
    if a['raw']['tw'] != b['raw']['tw']: c['slots differ'] += 1
    if a['clean'] != b['clean']: c['clean differs'] += 1
    rep = RU.noted(a, furtive=True)
    srv = set()
    if b['clean']:
        for d in (b['raw'].get('sv') or {}, b['raw'].get('svn') or {}):
            for i, ds in d.items():
                if ds and b['marks'][int(i)] != 'off': srv.add(int(i))
    if rep != srv: c['notes differ'] += 1; ex.append((k, sorted(rep - srv), sorted(srv - rep)))
    c['words noted (server)'] += len(srv); c['words noted (replay)'] += len(rep)
    for i, (ma, mb) in enumerate(zip(a['marks'], b['marks'])):
        if ma != mb:
            c[f'mark {ma or "-"} -> {mb or "-"}' + (' (was dropped)' if a['why'][i] == 'dropped' else '')] += 1
    c['red v5.5'] += a['marks'].count('off'); c['red v5.6'] += b['marks'].count('off')
for k, v in c.items(): print(f'  {k}: {v}')
for e in ex[:10]: print('  differs:', e)
