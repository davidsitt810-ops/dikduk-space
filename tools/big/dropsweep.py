"""The drop bar swept: on the skipped-word exam, the skipped word red / "not sure" / passed and the other words red;
on the correct reader's takes that had a red word (samra_drops), the words still red. Replayed from the rows' stored
rule inputs (drops.marks), the live rule first. usage: dropsweep.py [skip exam] [correct exam]"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drops as D
V = D.V
sk_name = sys.argv[1] if len(sys.argv) > 1 else 'samra_skip'; ok_name = sys.argv[2] if len(sys.argv) > 2 else 'samra_drops'
def load(nm):
    p = os.path.join(V, f'exam_{nm}.json')
    return [r for r in json.load(open(p, encoding='utf-8')) if 'raw' in r and 'rule_in' in r['raw']] if os.path.exists(p) else []
SK = [r for r in load(sk_name) if r.get('skip_ok')]; OK = load(ok_name)
print(f'{sk_name}: {len(SK)} takes with the skip in place; {ok_name}: {len(OK)} takes')
if SK:
    import statistics
    tops = []
    for r in SK:
        tw = r['raw']['rule_in']['tw']; j = r['planted'][0]
        ds = [t.get('drop') if t.get('drop') is not None else -1e9 for t in tw]
        others = [d for i, d in enumerate(ds) if i != j]
        tops.append((ds[j], max(others) if others else -1e9, r['clean'], r['marks'][j]))
    sj = sorted(t[0] for t in tops if t[0] > -1e8)
    print('   the skipped word\'s drop (nats): p10 %.1f  p25 %.1f  p50 %.1f  p75 %.1f' % tuple(sj[int(q * (len(sj) - 1))] for q in (.1, .25, .5, .75)))
    print('   ... clean takes %d of %d; skipped word the top drop on %d' % (sum(t[2] for t in tops), len(tops), sum(1 for t in tops if t[0] >= t[1])))
if OK:
    vals = []
    for r in OK:
        tw = r['raw']['rule_in']['tw']; m = r['marks']
        for i, x in enumerate(m):
            if x == 'off': vals.append((round(tw[i].get('drop') or -1, 1), r['why'][i], round(tw[i].get('skel') or 0, 2), round(tw[i].get('kept') or 0, 2), r['words'][i]))
    print('   correct reader, the red words now: (drop, why, skel, kept)', sorted(vals, key=lambda v: -v[0])[:60])
print(f'{"variant":28s} {"skipped red":>14s} {"not sure":>9s} {"passed":>7s} {"others red":>11s} {"correct: red":>13s}')
for v in ['-'] + [f'drop={d},margin={m}' for d in (10, 15, 20, 25, 30, 40) for m in (4, 8)] + ['hskel=0.7,hkept=0.5', 'hskel=0.6,hkept=0.5']:
    kw = D.parse(v); t = u = p = o = ow = 0
    for r in SK:
        m = D.marks(r, **kw); j = r['planted'][0]
        t += m[j] == 'off'; u += m[j] == 'unsure'; p += m[j] == 'ok'; o += sum(1 for i, x in enumerate(m) if x == 'off' and i != j); ow += len(m) - 1
    red = sum(1 for r in OK for x in D.marks(r, **kw) if x == 'off')
    n = max(1, len(SK))
    print(f'{v:28s} {t:5d} = {100*t/n:4.1f}% {u:9d} {p:7d} {o:5d} = {100*o/max(1,ow):.2f}% {red:13d}')
