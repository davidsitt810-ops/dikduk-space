"""The same takes through the server as recorded and as degraded (exam_voice.py DEGRADE=phone|noisy), paired by take
(perek, pasuk), both as the server marked them (v5.6 runs): how often the take is clean (vowel notes are shown on
clean takes only), each word's mark (✓ / not sure / red), and, for a planted exam, what the planted word got.
usage: phonecmp.py <exam as recorded> <exam degraded> [lo-hi]"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, drops as D
V = D.V; pct = D.pct

if __name__ == '__main__':
    a_name, b_name = sys.argv[1], sys.argv[2]; lo, hi = (int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else '1-150').split('-'))
    A = {(r['per'], r['ps']): r for r in RU.load(V, a_name, lo, hi)}; B = {(r['per'], r['ps']): r for r in RU.load(V, b_name, lo, hi)}
    keys = [k for k in sorted(set(A) & set(B)) if len(A[k]['words']) == len(B[k]['words'])]
    print(f'{a_name} vs {b_name}, perakim {lo}-{hi}: {len(keys)} takes in common')
    c = collections.Counter()
    for k in keys:
        ra, rb = A[k], B[k]; P = set(ra.get('planted') or [])
        c['clean_a'] += ra['clean']; c['clean_b'] += rb['clean']
        c['lost_clean'] += ra['clean'] and not rb['clean']; c['won_clean'] += rb['clean'] and not ra['clean']
        for nm, r in (('a', ra), ('b', rb)):
            for i, m in enumerate(r['marks']):
                g = 'p' if i in P else 'w'; c[(nm, g, m)] += 1; c[(nm, g, 'n')] += 1
            c[(nm, 'cant')] += bool(r.get('cant_hear')); c[(nm, 'line')] += bool(r.get('line_wrong'))
    n = len(keys)
    print(f'   clean takes {pct(c["clean_a"], n)} -> {pct(c["clean_b"], n)}   (clean only as recorded {c["lost_clean"]}, only degraded {c["won_clean"]})')
    for g, lab in (('w', 'other words' if any(A[k].get('planted') for k in keys) else 'words'), ('p', 'planted words')):
        na, nb = c[('a', g, 'n')], c[('b', g, 'n')]
        if not na: continue
        print(f'   {lab}: ✓ {pct(c[("a", g, "ok")], na)} -> {pct(c[("b", g, "ok")], nb)};  not sure {pct(c[("a", g, "unsure")], na)} -> {pct(c[("b", g, "unsure")], nb)};  red {pct(c[("a", g, "off")], na)} -> {pct(c[("b", g, "off")], nb)}')
    print(f"   can't hear {c[('a', 'cant')]} -> {c[('b', 'cant')]};  line called wrong {c[('a', 'line')]} -> {c[('b', 'line')]}")
