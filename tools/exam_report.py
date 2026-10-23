"""One report for both exams (exam_rows.json = Rabbi Alouf's Tehillim; exam_archive_rows.json = the pizmonim archive,
another hazzan against the site's reference): the rule applied offline from the rows' signals, with the CLEAN gate as
shipped (median letter-head score >= .7) and with the robust gate (the lowest word left out of the median when the
line has 3+ scoreable words). usage: exam_report.py [rows.json ...]"""
import sys, os, json, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
RULE = {'drop': 10, 'margin': 4, 'swap': 8, 'gap': 0.6}
def mark_of(r, clean):
    n = r.get('n') or 0; sk = r.get('skel'); ft = r.get('fit'); kp = r.get('kept'); pw = r.get('pw'); hs = r.get('hskel')
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
def hs_of(TW): return sorted(t['hskel'] for t in TW if (t.get('n') or 0) >= 2 and t.get('hskel') is not None)
def gate_now(TW): hs = hs_of(TW); return bool(hs) and hs[len(hs) // 2] >= .7
def gate_robust(TW):
    hs = hs_of(TW)
    if len(hs) < 3: return gate_now(TW)
    h = hs[1:]; return h[len(h) // 2] >= .7
def line_marks(TW, clean):
    marks = [mark_of(t, clean) for t in TW]; why = [''] * len(TW); lw = False
    if clean:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        if (TW[top].get('n') or 0) >= 2 and ds[top] >= RULE['drop'] and ds[top] - second >= RULE['margin']: marks[top] = 'off'; why[top] = 'dropped'
        sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if sw:
            j = int(np.argmax(sw)); na, nb = TW[j].get('n') or 0, TW[j + 1].get('n') or 0
            if sw[j] >= RULE['swap'] and max(na, nb) >= 2 and min(na, nb) >= 1: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
        if TW[0].get('gap') is not None and TW[0]['gap'] >= RULE['gap']: lw = True; marks = ['unsure' if m == 'ok' else m for m in marks]
    return marks, why, lw
def lines_of(R):
    L = collections.defaultdict(dict)
    for r in R: L[(r['case'], r.get('per', r.get('pid')), r.get('ps', r.get('line')), r.get('rec', ''))][r['k']] = r
    return {k: [v[i] for i in sorted(v)] for k, v in L.items()}
def run(R, gate, label, cases):
    L = lines_of(R); res = {}; fa = []; lw_by = collections.Counter(); n_by = collections.Counter(); clean_by = collections.Counter()
    for key, TW in L.items():
        clean = gate(TW); marks, why, lw = line_marks(TW, clean); case = key[0]
        n_by[case] += 1; lw_by[case] += lw; clean_by[case] += clean
        for t, m in zip(TW, marks):
            if (t.get('n') or 0) < 1: continue
            c = res.setdefault(case, {'good': collections.Counter(), 'bad': collections.Counter()})
            c['bad' if t['bad'] else 'good'][m or 'ok'] += 1
            if not t['bad'] and m == 'off' and case != 'wrongline': fa.append((key, t['w']))
    print(f'\n  [{label}]')
    for case in cases:
        if case not in res: continue
        g = res[case]['good']; b = res[case]['bad']; ng = sum(g.values()); nb = sum(b.values())
        s = f'    {case:9s} lines {n_by[case]:3d} (clean {clean_by[case]}, line-wrong {lw_by[case]})'
        if ng: s += f' | right {ng:4d}: red {g["off"]} ({100 * g["off"] / ng:.1f}%), unsure {g["unsure"]} ({100 * g["unsure"] / ng:.0f}%)'
        if nb: s += f' | wrong {nb:4d}: caught {b["off"]} ({100 * b["off"] / nb:.0f}%), unsure {b["unsure"]} ({100 * b["unsure"] / nb:.0f}%), passed {b["ok"]} ({100 * b["ok"] / nb:.0f}%)'
        print(s)
    if fa: print('    false alarms:', fa[:10], '' if len(fa) <= 10 else f'... {len(fa)}')
    return res
files = sys.argv[1:] or [os.path.join(HERE, 'exam_rows.json'), os.path.join(HERE, 'exam_archive_rows.json')]
for f in files:
    if not os.path.exists(f): print('no', f); continue
    R = json.load(open(f, encoding='utf-8'))
    cases = ('intact', 'right', 'skip', 'swap', 'wrongword', 'wrongline')
    print(f'\n== {os.path.basename(f)}: {len(R)} rows')
    if 'seen' in R[0]:
        # the archive exam: which takes' recordings the letter head was trained on (manifest.jsonl)
        try:
            seen = set((str(json.loads(l)['pid']), json.loads(l)['rec']) for l in open(os.path.join(HERE, 'manifest.jsonl'), encoding='utf-8') if '"ar"' in l)
            for r in R: r['seen'] = (str(r['pid']), r['rec']) in seen
            print(f"   takes on recordings the head was trained on: {sum(1 for r in R if r['seen'] and r['k'] == 0)} of {sum(1 for r in R if r['k'] == 0)}")
        except Exception as e: print('   (manifest not read:', e, ')')
    for gate, label in ((gate_now, 'CLEAN gate as shipped'), (gate_robust, 'robust CLEAN gate')):
        run(R, gate, label, cases)
    if 'seen' in R[0]:
        for gate, label in ((gate_now, 'unseen recordings only, gate as shipped'), (gate_robust, 'unseen recordings only, robust gate')):
            run([r for r in R if not r['seen']], gate, label, cases)
