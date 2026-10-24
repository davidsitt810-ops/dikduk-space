"""The checker examined on Rabbi Alouf's held-out perakim (never used to train the heads): every pasuk intact, and
tampered the way a student errs — a word left out (its audio cut), two neighbours swapped (their audio swapped),
a word replaced (its audio replaced by another word's from the same perek), and the whole pasuk read as another
pasuk. The reference hazzan is his own intact pasuk, as on the Space. Every word's signals and the truth go to
exam_rows.json; throat verdicts and vowel notes of the intact pesukim to exam_lines.json.
usage: exam_alouf.py [pesukim=70] [seed=5]"""
import sys, os, json, time, random, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
import numpy as np
import app
from nikud import parse_verse
from vowels import compare_vowels
HERE = os.path.dirname(os.path.abspath(__file__)); N = int(sys.argv[1]) if len(sys.argv) > 1 else 70; SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 5
random.seed(SEED)
PER = [7, 12, 18, 21, 23, 32, 35, 40, 46, 94, 118, 123, 126, 140]   # held out by train_head2 (seed 0)
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
SR = 16000
def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(HERE, '..', 'alouf', 'mp3', fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()
def skel(w): return ''.join(c for c in app.he_read(w) if c not in 'אהוי')
jobs = []
for n in PER:
    rec = IDX['perakim'][str(n)]
    for i, p in enumerate(rec['pesukim']):
        if p['t0'] is None or p['t1'] - p['t0'] > 14 or len(p['words']) < 4 or any(w['t0'] is None for w in p['words']): continue
        jobs.append((n, rec, i))
random.shuffle(jobs)
if os.environ.get('EXCLUDE'):   # a validation batch: leave out the pesukim of an earlier exam
    done = set((r['per'], r['ps']) for r in json.load(open(os.environ['EXCLUDE'], encoding='utf-8')))
    jobs = [j for j in jobs if (j[0], j[2]) not in done]
jobs = jobs[:N]
OUT = os.environ.get('EXAM_OUT', 'exam')
print(f'{len(jobs)} pesukim from {len(PER)} held-out perakim', flush=True)
rows, lines = [], []; t_start = time.time()
def seg(x, off, a, b): return x[int(max(0, (a - off)) * SR):int((b - off) * SR)]
def add_rows(case, n, i, take, fit, tampered, ref):
    hs = sorted(t['hskel'] for t in take['words'] if (t.get('n') or 0) >= 2 and t.get('hskel') is not None); clean = bool(hs) and hs[len(hs) // 2] >= .7
    for k, w in enumerate(take['words']):
        f = fit[k] if fit else {}
        rows.append({'case': case, 'per': n, 'ps': i, 'k': k, 'nw': len(take['words']), 'bad': 1 if k in tampered else 0, 'w': w['w'], 'n': w['n'], 'skel': w['skel'], 'fit': f.get('fit'), 'hskel': w.get('hskel'), 'vskel': w.get('vskel'),
                     'kept': w.get('kept'), 'pw': app.word_pw(w), 'drop': w.get('drop'), 'swap': w.get('swap'), 'drop_ph': w.get('drop_ph'), 'swap_ph': w.get('swap_ph'), 'gap': take.get('gap'), 'gap_ph': take.get('gap_ph'), 'clean': clean,
                     'selffit': (ref['words'][k].get('selffit') if ref and k < len(ref['words']) else None), 'dur': round(w['t1'] - w['t0'], 3)})
for done, (n, rec, i) in enumerate(jobs, 1):
    p = rec['pesukim'][i]; off = p['t0'] - .2; x = cut(rec['original'], off, p['t1'] + .2)
    if x.shape[0] < SR: continue
    W = [w.get('said', w['w']) for w in p['words']]; wt = [(w['t0'], w['t1']) for w in p['words']]
    ref, lp_r, spf_r = app.analyse(x, W); sf = app.fit_against(lp_r, spf_r, ref['words'])
    for w, s in zip(ref['words'], sf): w['selffit'] = s.get('fit')
    def check(xx, WW, R=ref):
        take, lp, spf = app.analyse(xx, WW); return take, (app.fit_against(lp, spf, R['words']) if R else None)
    # intact (the reference is itself): words, throat verdicts, vowels against the nikud
    add_rows('intact', n, i, ref, sf, set(), ref)
    try:
        exp = {j: [{'heard': u['c']} for u in us if u['kind'] == 'vowel'] for j, (_, _, us) in enumerate(parse_verse(p['nikud']))}
        vn = compare_vowels({j: w.get('vow', []) for j, w in enumerate(ref['words'])}, exp) if len(exp) == len(W) else None
    except Exception as e:
        vn = {'err': str(e)[:80]}
    lines.append({'per': n, 'ps': i, 'words': W, 'gap': ref.get('gap'), 'gap_ph': ref.get('gap_ph'), 'ms': ref['ms'], 'dur': ref['dur'],
                  'throat': [{'w': w['w'], 'c': th['c'], 'k': th['k'], 'pos': 'start' if th['k'] == 0 else ('end' if th['k'] == len(app.he_read(w['w'])) - 1 else 'mid'), 'v': th.get('v'), 'p': th.get('p'), 'p2': th.get('p2'), 'ar': th.get('ar_heard'), 'head': (th.get('head') or {}).get('heard')} for w in ref['words'] for th in w.get('throat', [])],
                  'vowel_notes': {str(k): v for k, v in (vn or {}).items()} if isinstance(vn, dict) else vn, 'nvow': sum(len(w.get('vow', [])) for w in ref['words'])})
    # a word left out
    cands = [j for j in range(1, len(W) - 1) if ref['words'][j]['n'] >= 2]
    if cands:
        j = random.choice(cands); a, b = wt[j]
        xs = np.concatenate([seg(x, off, off, a), seg(x, off, b, p['t1'] + .2)]); tk, ft = check(xs, W); add_rows('skip', n, i, tk, ft, {j}, ref)
    # two neighbours swapped
    cands = [j for j in range(0, len(W) - 1) if ref['words'][j]['n'] >= 2 and ref['words'][j + 1]['n'] >= 2 and wt[j][1] <= wt[j + 1][0] + 1e-3]
    if cands:
        j = random.choice(cands); (a1, b1), (a2, b2) = wt[j], wt[j + 1]
        xs = np.concatenate([seg(x, off, off, a1), seg(x, off, a2, b2), seg(x, off, b1, a2), seg(x, off, a1, b1), seg(x, off, b2, p['t1'] + .2)]); tk, ft = check(xs, W); add_rows('swap', n, i, tk, ft, {j, j + 1}, ref)
    # a word replaced by another word's audio (same perek, similar length, different skeleton)
    cands = [j for j in range(0, len(W)) if ref['words'][j]['n'] >= 2]
    if cands:
        j = random.choice(cands); d = wt[j][1] - wt[j][0]; pool = []
        for q in rec['pesukim']:
            if q is p or q['t0'] is None: continue
            for v in q['words']:
                if v['t0'] is None: continue
                dv = v['t1'] - v['t0']
                if 0.7 * d <= dv <= 1.3 * d and skel(v.get('said', v['w'])) != skel(W[j]) and len(skel(v.get('said', v['w']))) >= 2: pool.append((q, v))
        if pool:
            q, v = random.choice(pool); xr = cut(rec['original'], v['t0'], v['t1'])
            xs = np.concatenate([seg(x, off, off, wt[j][0]), xr, seg(x, off, wt[j][1], p['t1'] + .2)]); tk, ft = check(xs, W); add_rows('wrongword', n, i, tk, ft, {j}, ref)
            rows[-len(W) + j]['replaced_by'] = v.get('said', v['w'])
    # the whole pasuk read as another pasuk of the same perek
    others = [q for q in rec['pesukim'] if q is not p and q['t0'] is not None and abs(len(q['words']) - len(W)) <= 2]
    if others:
        q = random.choice(others); Wq = [w.get('said', w['w']) for w in q['words']]
        xq = cut(rec['original'], q['t0'] - .2, q['t1'] + .2); rq, lpq, spfq = app.analyse(xq, Wq); sfq = app.fit_against(lpq, spfq, rq['words'])
        for w, s in zip(rq['words'], sfq): w['selffit'] = s.get('fit')
        tk, ft = check(x, Wq, rq); add_rows('wrongline', n, i, tk, ft, set(range(len(Wq))), rq)
    if done % 5 == 0:
        print(f'{done}/{len(jobs)} pesukim · {int(time.time() - t_start)} s · rows {len(rows)}', flush=True)
        json.dump(rows, open(os.path.join(HERE, OUT + '_rows.json'), 'w'), ensure_ascii=False); json.dump(lines, open(os.path.join(HERE, OUT + '_lines.json'), 'w'), ensure_ascii=False)
json.dump(rows, open(os.path.join(HERE, OUT + '_rows.json'), 'w'), ensure_ascii=False); json.dump(lines, open(os.path.join(HERE, OUT + '_lines.json'), 'w'), ensure_ascii=False)
print('done', len(rows), 'word rows,', len(lines), 'intact pesukim,', int(time.time() - t_start), 's')
