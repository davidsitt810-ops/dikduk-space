"""One report for both exams — exam_rows.json (Rabbi Alouf's Tehillim: intact / skip / swap / wrongword / wrongline)
and exam_archive_rows.json (the pizmonim archive: another hazzan's right take against the site's reference, plus
skip / swap / wrongline). The rule is taken from app.py itself (mark_of, marks_of, clean_of: the server's copy, which
t_parity.py checks against the page's and the embed's JS), and the v4.3 rule is kept here for the before/after.
usage: exam_report.py [rows.json ...]"""
import sys, os, json, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
# ---- the live rule, out of app.py without loading the models
src = open(os.path.join(HERE, '..', 'space', 'app.py'), encoding='utf-8').read()
def pyfn(name, stop): i = src.index(f'def {name}('); j = src.index(stop, i); return src[i:j]
code = 'import numpy as np\n' + src[src.index("RULE = {'drop'"):src.index('\ndef head_median')] + '\n' + pyfn('mark_of', '\nRULE = ') + pyfn('head_median', '\ndef clean_of') + pyfn('clean_of', '\ndef marks_of') + pyfn('marks_of', '\ndef summarize')
LIVE = {}; exec(code, LIVE)
def live_marks(TW):
    F = [{'fit': t.get('fit')} for t in TW] if any(t.get('fit') is not None for t in TW) else None
    rival = {'gain': TW[0]['rival']} if TW and TW[0].get('rival') is not None else None   # rows from exams that scored the text's other lines carry it
    clean = LIVE['clean_of'](TW); marks, why, lw, cant = LIVE['marks_of'](TW, F, TW[0].get('gap'), clean, rival); return marks, why, lw, cant, clean
# ---- v4.3 as shipped on Oct 23 morning, for the before/after
RULE43 = {'drop': 10, 'margin': 4, 'swap': 8, 'gap': 0.6}
def mark_of43(r, clean):
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
def v43_marks(TW):
    hs = sorted(t['hskel'] for t in TW if (t.get('n') or 0) >= 2 and t.get('hskel') is not None); clean = bool(hs) and hs[len(hs) // 2] >= .7
    marks = [mark_of43(t, clean) for t in TW]; why = [''] * len(TW); lw = False
    if clean:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        if (TW[top].get('n') or 0) >= 2 and ds[top] >= RULE43['drop'] and ds[top] - second >= RULE43['margin']: marks[top] = 'off'; why[top] = 'dropped'
        sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if sw:
            j = int(np.argmax(sw)); na, nb = TW[j].get('n') or 0, TW[j + 1].get('n') or 0
            if sw[j] >= RULE43['swap'] and max(na, nb) >= 2 and min(na, nb) >= 1: marks[j] = marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'
        if TW[0].get('gap') is not None and TW[0]['gap'] >= RULE43['gap']: lw = True; marks = ['unsure' if m == 'ok' else m for m in marks]
    return marks, why, lw, False, clean
def lines_of(R):
    L = collections.defaultdict(dict)
    for r in R: L[(r['case'], r.get('per', r.get('pid', r.get('f'))), r.get('ps', r.get('line', 0)), r.get('rec', ''))][r['k']] = r
    return {k: [v[i] for i in sorted(v)] for k, v in L.items()}
CASES = ('intact', 'right', 'skip', 'swap', 'wrongword', 'wrongline')
def run(R, fn, label, show_fa=True):
    L = lines_of(R); res = {}; fa = []; n_by = collections.Counter(); lw_by = collections.Counter(); cant_by = collections.Counter(); clean_by = collections.Counter()
    for key, TW in L.items():
        marks, why, lw, cant, clean = fn(TW); case = key[0]
        n_by[case] += 1; lw_by[case] += lw; cant_by[case] += cant; clean_by[case] += clean
        for t, m in zip(TW, marks):
            if (t.get('n') or 0) < 1: continue
            c = res.setdefault(case, {'good': collections.Counter(), 'bad': collections.Counter()})
            c['bad' if t['bad'] else 'good'][m or 'ok'] += 1
            if not t['bad'] and m == 'off' and case != 'wrongline': fa.append((key[1], key[2] + 1, key[3], t['w']))
    print(f'\n  [{label}]')
    for case in CASES:
        if case not in res: continue
        g = res[case]['good']; b = res[case]['bad']; ng = sum(g.values()); nb = sum(b.values())
        s = f'    {case:9s} takes {n_by[case]:3d} (clean {clean_by[case]}, line-wrong {lw_by[case]}, cannot-hear {cant_by[case]})'
        if ng: s += f' | right {ng:4d}: red {g["off"]} ({100 * g["off"] / ng:.1f}%), unsure {g["unsure"]} ({100 * g["unsure"] / ng:.0f}%)'
        if nb: s += f' | wrong {nb:4d}: caught {b["off"]} ({100 * b["off"] / nb:.0f}%), unsure {b["unsure"]} ({100 * b["unsure"] / nb:.0f}%), passed {b["ok"]} ({100 * b["ok"] / nb:.0f}%)'
        print(s)
    if fa and show_fa: print('    red on a right word:', fa[:12], '' if len(fa) <= 12 else f'... {len(fa)}')
    return res
if __name__ == '__main__':
    files = sys.argv[1:] or [os.path.join(HERE, 'exam_rows.json'), os.path.join(HERE, 'exam_archive_rows.json')]
    for f in files:
        if not os.path.exists(f): print('no', f); continue
        R = json.load(open(f, encoding='utf-8'))
        print(f'\n== {os.path.basename(f)}: {len(R)} rows')
        if 'pid' in R[0]:
            # the archive: a right take whose clip cannot hold the line (sync events) is left out, and takes on recordings the head trained on are counted
            try:
                tsrc = open(os.path.join(HERE, 'exam_archive_truth.py'), encoding='utf-8').read().split('def plausible')[0]
                tns = {'__file__': os.path.join(HERE, 'exam_archive_truth.py')}; exec(tsrc, tns); T = tns['T']
                bad = set((t['pid'], t['line'], t['rec']) for t in T if t['case'] == 'right' and not (0.5 * t['ref_dur'] <= t['dur'] <= 2.0 * t['ref_dur']))
                R = [r for r in R if not (r['case'] == 'right' and (r['pid'], r['line'], r['rec']) in bad)]
                print(f'   right takes whose clip cannot hold the line, left out: {len(bad)}')
            except Exception as e: print('   (takes not read:', e, ')')
            try:
                seen = set((str(json.loads(l)['pid']), json.loads(l)['rec']) for l in open(os.path.join(HERE, 'manifest.jsonl'), encoding='utf-8') if '"ar"' in l)
                print(f"   takes on recordings the letter head was trained on: {sum(1 for r in R if (str(r['pid']), r['rec']) in seen and r['k'] == 0)} of {sum(1 for r in R if r['k'] == 0)}")
            except Exception as e: print('   (manifest not read:', e, ')')
        run(R, v43_marks, 'v4.3 (Oct 23 morning)', show_fa=False)
        run(R, live_marks, 'the rule in app.py now')
