"""The current shipped rule (app.marks_of, v4.3 + short-word swaps) on the exam rows: what is still missed, and what
the missed words' signals look like next to the right words'. usage: exam_misses.py [exam_rows.json]"""
import sys, os, json, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'exam_rows.json')))
RULE = {'drop': 10, 'margin': 4, 'swap': 8, 'gap': 0.6}
def mark_of(r, clean):
    n = r['n'] or 0; sk = r['skel']; ft = r['fit']; kp = r['kept']; pw = r['pw']; hs = r.get('hskel')
    if not n or sk is None: return ''
    sure = clean and kp is not None and kp >= .75 and hs is not None and hs >= .6 and (pw is None or pw < .8)
    if n >= 2:
        if sk < .2 and (ft is None or ft < .15):
            if ft is None and clean and not (kp is not None and kp < .75): return 'unsure'
            return 'off'
        if clean and pw is not None and pw >= .95: return 'off'
        if sure: return 'ok'
        if sk < .4 or (ft is not None and ft < .2) or (kp is not None and kp < .5) or (pw is not None and pw >= .8): return 'unsure'
        return 'ok'
    return 'unsure' if sk < .2 and not sure else 'ok'
lines = collections.defaultdict(dict)
for r in R: lines[(r['case'], r['per'], r['ps'])][r['k']] = r
def line_marks(TW):
    clean = TW[0]['clean']; marks = [mark_of(t, clean) for t in TW]; why = [''] * len(TW); lw = False
    if clean:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        if (TW[top]['n'] or 0) >= 2 and ds[top] >= RULE['drop'] and ds[top] - second >= RULE['margin']: marks[top] = 'off'; why[top] = 'dropped'
        sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if sw:
            j = int(np.argmax(sw)); na, nb = TW[j]['n'] or 0, TW[j + 1]['n'] or 0
            if sw[j] >= RULE['swap'] and max(na, nb) >= 2 and min(na, nb) >= 1: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
        if TW[0].get('gap') is not None and TW[0]['gap'] >= RULE['gap']: lw = True; marks = ['unsure' if m == 'ok' else m for m in marks]
    return marks, why, lw
res = collections.defaultdict(collections.Counter); missed = collections.defaultdict(list); fa = []
for key, rows in lines.items():
    ks = sorted(rows); TW = [rows[k] for k in ks]; marks, why, lw = line_marks(TW)
    for t, m in zip(TW, marks):
        if (t['n'] or 0) < 1: continue
        res[(key[0], 'bad' if t['bad'] else 'good')][m or 'ok'] += 1
        if t['bad'] and m != 'off' and key[0] != 'wrongline': missed[key[0]].append((t, m, TW))
        if not t['bad'] and m == 'off' and key[0] != 'wrongline': fa.append((t, key))
for case in ('intact', 'skip', 'swap', 'wrongword', 'wrongline'):
    g = res[(case, 'good')]; b = res[(case, 'bad')]; ng = sum(g.values()); nb = sum(b.values())
    print(f'{case:10s} right {ng:4d}: red {g["off"]}, unsure {g["unsure"]} ({100 * g["unsure"] / max(1, ng):.1f}%)' + (f' | wrong {nb:3d}: caught {b["off"]} ({100 * b["off"] / nb:.0f}%), unsure {b["unsure"]} ({100 * b["unsure"] / nb:.0f}%), passed {b["ok"]} ({100 * b["ok"] / nb:.0f}%)' if nb else ''))
print('false alarms:', [(t['w'], key) for t, key in fa])
def sig(t): return f"n={t['n']} skel={t['skel']:.2f} fit={t['fit'] if t['fit'] is None else round(t['fit'], 2)} kept={t['kept']} pw={t['pw'] if t['pw'] is None else round(t['pw'], 2)} drop={round(t['drop'], 1) if t.get('drop') is not None else None} swap={round(t['swap'], 1) if t.get('swap') is not None else None} gap={t['gap']:.2f} dur={t['dur']}"
for case in ('skip', 'wrongword', 'swap'):
    print(f'\n--- {case}: missed {len(missed[case])}')
    for t, m, TW in sorted(missed[case], key=lambda x: -(x[0].get('drop') or -99)):
        ds = sorted((x['drop'] for x in TW if x.get('drop') is not None), reverse=True); second = ds[1] if len(ds) > 1 else None
        rb = t.get('replaced_by', '')
        print(f"  {t['per']}:{t['ps'] + 1} {t['w']:10s} {('->' + rb) if rb else '':12s} mark={m:6s} {sig(t)} line top drop={ds[0]:.1f} second={second}")
# where do the missed replaced words sit in the right-word distributions?
good = [r for r in R if not r['bad'] and r['case'] != 'wrongline' and (r['n'] or 0) >= 2 and r['clean']]
print('\nright words (clean, n>=2):', len(good))
for name, f in (('drop', lambda r: r.get('drop')), ('skel', lambda r: r['skel']), ('kept', lambda r: r['kept']), ('pw', lambda r: r['pw']), ('fit', lambda r: r['fit'])):
    v = np.array([f(r) for r in good if f(r) is not None]); print(f'  {name:5s} p50 {np.percentile(v, 50):.2f} p95 {np.percentile(v, 95):.2f} p99 {np.percentile(v, 99):.2f} max {v.max():.2f} min {v.min():.2f}')
# candidate: a second-tier rule for words the drop alone does not settle: drop >= 6 and (skel < .3 or kept <= .5)
def tier2(t, TW):
    if (t['n'] or 0) < 2 or not t['clean'] or t.get('drop') is None: return False
    return t['drop'] >= 6 and (t['skel'] < .3 or (t['kept'] is not None and t['kept'] <= .5))
fa2 = [(r['w'], r['case'], r['per'], r['ps'] + 1, round(r['drop'], 1), r['skel'], r['kept']) for key, rows in lines.items() if key[0] != 'wrongline' for r in rows.values() if not r['bad'] and tier2(r, rows)]
c2 = collections.Counter(); n2 = collections.Counter()
for case in ('skip', 'wrongword', 'swap'):
    for t, m, TW in missed[case]:
        n2[case] += 1; c2[case] += tier2(t, TW)
print('\ntier-2 candidate (drop >= 6 and (skel < .3 or kept <= .5)): extra catches', dict(c2), 'of missed', dict(n2), '| false alarms on right words:', len(fa2), fa2[:12])
