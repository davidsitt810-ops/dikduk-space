"""A skipped-word exam (PLANT=SKIP) under the live rule (v5.5) and the drop bar at 20 (v5.6), from the stored rule
inputs: the skipped word red / "not sure" / passed on clean takes and on the rest, strict (a clean take's "not sure"
counts as ✕), and by how long the cut was. usage: skipstats.py <skip exam> [...]"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drops as D

def table(rows, drop):
    c = collections.Counter()
    for r in rows:
        m = D.marks(r, drop=drop) if drop else r['marks']; j = r['planted'][0]; x = m[j]
        cl = 'clean' if r['clean'] else 'rest'
        c[(cl, x)] += 1; c[(cl, 'n')] += 1
        if r['clean']: c[('strict', 'off' if x in ('off', 'unsure') else x)] += 1; c[('strict', 'n')] += 1
        d = r['skip_t'][1] - r['skip_t'][0]; b = '<0.2 s' if d < .2 else '0.2-0.4 s' if d < .4 else '>=0.4 s'
        c[(b, x)] += 1; c[(b, 'n')] += 1
    return c

if __name__ == '__main__':
    for name in sys.argv[1:]:
        rows = [r for r in json.load(open(os.path.join(D.V, f'exam_{name}.json'), encoding='utf-8')) if r.get('skip_ok') and 'rule_in' in r.get('raw', {})]
        print(f'{name}: {len(rows)} takes with the skip in place')
        for lab, drop in (('v5.5 (drop 10)', None), ('v5.6 (drop 20)', 20)):
            c = table(rows, drop); print('  ' + lab)
            for g in ('clean', 'rest', 'strict', '<0.2 s', '0.2-0.4 s', '>=0.4 s'):
                n = c[(g, 'n')]
                if n: print(f'    {g:10s} n={n:4d}  red {100*c[(g,"off")]/n:5.1f}%  not sure {100*c[(g,"unsure")]/n:5.1f}%  passed {100*c[(g,"ok")]/n:5.1f}%')
