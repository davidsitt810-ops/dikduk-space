"""Which "you said i, the page says e" notes to keep: Faraj's correct reading (every e->i note a false alarm; David
heard a clear e) against Faraj with the page's hiriq written tsere (PLANT=IE: every planted word a real i where the
page says e, which a note should catch). Rule A (live) plus variants that keep an e->i note only when "very sure".
usage: ei_rules.py correct.json planted_ie.json [planted_ou.json ...]"""
import sys, os, json, collections
V = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, V)
import false_notes as FN
import numpy as np

def score(rows, keep):
    """-> (words with a note on unplanted words, planted words told, planted words)"""
    other = told = pw = 0
    for r in rows:
        if 'raw' not in r or 'words' not in r: continue
        P = set(r.get('planted') or [])
        ns = [n for n in FN.notes_detail(r) if keep(r, n)]; W = {n['w'] for n in ns}
        pw += len(P); told += sum(1 for i in P if i in W or r['marks'][i] == 'off'); other += len(W - P)
    return other, told, pw

def slot_mass(r, n):
    for s in r['raw']['tw'][n['w']]:
        if s[1] == n['you'] and abs((s[3] or 0) - (n['p'] or 0)) < 1e-9: return s[2]
    return {}

def rule(min_m=0.0, min_i=0.0, max_e=1.0, min_p=0.0):
    def keep(r, n):
        if not (n['ref'] == 'E' and n['you'] == 'I'): return True
        m = slot_mass(r, n); tot = sum(m.values()) or 1e-9
        return m.get('I', 0) / tot >= min_m and m.get('I', 0) >= min_i and m.get('E', 0) / tot <= max_e and (n['p'] or 0) >= min_p
    return keep

if __name__ == '__main__':
    files = sys.argv[1:]
    data = {os.path.basename(f): [r for r in json.load(open(f, encoding='utf-8')) if 'raw' in r and 'words' in r] for f in files}
    # how the two kinds of e->i note look
    for name, rows in data.items():
        planted = any(r.get('planted') is not None for r in rows)
        ms, es, ts, ps = [], [], [], []
        for r in rows:
            P = set(r.get('planted') or [])
            for n in FN.notes_detail(r):
                if n['ref'] == 'E' and n['you'] == 'I' and ((n['w'] in P) == planted):
                    m = slot_mass(r, n); tot = sum(m.values()) or 1e-9
                    ms.append(m.get('I', 0) / tot); es.append(m.get('E', 0) / tot); ts.append(m.get('I', 0)); ps.append(n['p'] or 0)
        if ms:
            q = lambda a: ' '.join(f'{x:.3f}' for x in np.percentile(a, [10, 25, 50, 75, 90]))
            print(f'{name}: {len(ms)} e->i notes ({"planted real i" if planted else "false: a clear e"})\n   share m p10..p90 {q(ms)}\n   E share {q(es)}\n   I mass {q(ts)}\n   slot p {q(ps)}')
    RULES = [('A (live)', lambda r, n: True), ('no e->i', rule(min_m=2)), ('m>=.99', rule(min_m=.99)), ('m>=.995', rule(min_m=.995)),
             ('m>=.999', rule(min_m=.999)), ('I mass>=1.0', rule(min_i=1.0)), ('I mass>=1.5', rule(min_i=1.5)), ('I mass>=2.0', rule(min_i=2.0)),
             ('p>=.95', rule(min_p=.95)), ('m>=.99 & p>=.95', rule(min_m=.99, min_p=.95))]
    print()
    for label, keep in RULES:
        cells = []
        for name, rows in data.items():
            o, t, pw = score(rows, keep)
            cells.append(f'{name.replace("exam_", "").replace(".json", "")}: ' + (f'told {t}/{pw} ({100 * t / pw:.1f}%), other words noted {o}' if pw else f'words noted {o}'))
        print(f'{label:18s} ' + ' | '.join(cells))
