"""Why marks changed between a v5.5 exam and the v5.6 run: the v5.5 'why' and rule inputs for each changed word,
and the v5.5 mark of each word whose vowel note the v5.6 server shows but the replay doesn't."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A = {(r['per'], r['ps']): r for r in RU.load(V, sys.argv[1])}; B = {(r['per'], r['ps']): r for r in RU.load(V, sys.argv[2])}
c = collections.Counter()
for k in sorted(set(A) & set(B)):
    a, b = A[k], B[k]
    tw = {t['n']: t for t in (a['raw'].get('rule_in') or {}).get('tw', [])}
    for i, (ma, mb) in enumerate(zip(a['marks'], b['marks'])):
        if ma != mb:
            c[(ma, mb, a['why'][i], b['why'][i])] += 1
            if ma == 'unsure':
                t = tw.get(i, {})
                print(k, i, ma, '->', mb, 'why', a['why'][i], '->', b['why'][i], {x: t.get(x) for x in ('kept', 'pw', 'drop', 'swap')})
for x, n in c.most_common(): print(n, x)
