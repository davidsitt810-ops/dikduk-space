"""Calibrate the rival-line evidence (order.rival_evidence): on Rabbi Alouf's held-out pesukim, the right pasuk against
the other pesukim of its perek (RIGHT: the written line should win) and the audio checked as another pasuk with the
true one among the alternatives (WRONG LINE: the true one should win by a lot); on the Israeli sentences the same
with five other sentences as alternatives. Also the free-path gap of each take, to see the two side by side.
usage: calib_rival.py [alouf pesukim=70] [israeli sentences=80]"""
import sys, os, json, glob, time, random, subprocess, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app
from order import rival_evidence
HERE = os.path.dirname(os.path.abspath(__file__)); random.seed(7)
NA = int(sys.argv[1]) if len(sys.argv) > 1 else 70; NI = int(sys.argv[2]) if len(sys.argv) > 2 else 80
PER = [7, 12, 18, 21, 23, 32, 35, 40, 46, 94, 118, 123, 126, 140]
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(HERE, '..', 'alouf', 'mp3', fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()
def head_of(x):
    if app.FT is not None: return app.ft_lps(x)[0]
    ar_lp, ar_spf, AH = app.arabic_lp(x); return app.head_lp(AH)
rows = []; t_start = time.time()
jobs = []
for n in PER:
    rec = IDX['perakim'][str(n)]
    for i, p in enumerate(rec['pesukim']):
        if p['t0'] is None or p['t1'] - p['t0'] > 12 or len(p['words']) < 4: continue
        jobs.append((n, rec, i))
random.shuffle(jobs)
for n, rec, i in jobs[:NA]:
    p = rec['pesukim'][i]; x = cut(rec['original'], p['t0'] - .2, p['t1'] + .2)
    W = [w.get('said', w['w']) for w in p['words']]
    allW = [[w.get('said', w['w']) for w in q['words']] for q in rec['pesukim'] if q['words']]
    try: hlp = head_of(x)
    except Exception as e: print('fail', n, i, e, flush=True); continue
    ev = app.order_evidence(hlp, W, app.HEAD_S2I, app.he_read, 0)
    rv = rival_evidence(hlp, W, [a for a in allW if a != W], app.HEAD_S2I, app.he_read)
    rows.append({'set': 'alouf', 'case': 'right', 'per': n, 'ps': i, 'gap': ev['gap'], 'rival': rv and rv['gain'], 'n_alts': rv and rv['n']})
    others = [a for a in allW if a != W and abs(len(a) - len(W)) <= 2]
    if others:
        Wo = random.choice(others)
        ev2 = app.order_evidence(hlp, Wo, app.HEAD_S2I, app.he_read, 0)
        rv2 = rival_evidence(hlp, Wo, [a for a in allW if a != Wo], app.HEAD_S2I, app.he_read)
        rows.append({'set': 'alouf', 'case': 'wrongline', 'per': n, 'ps': i, 'gap': ev2['gap'], 'rival': rv2 and rv2['gain'], 'n_alts': rv2 and rv2['n']})
print(f'alouf done: {len(rows)} rows, {int(time.time() - t_start)} s', flush=True)
meta = json.load(open(os.path.join(HERE, '..', 'fleurs', 'dev.json'), encoding='utf-8')); by = {r[1]: r[3] for r in meta}
wavs = sorted(glob.glob(os.path.join(HERE, '..', 'fleurs_fresh', 'dev', '*.wav')))
texts = [app.he_words(by[os.path.basename(w)]) for w in wavs if by.get(os.path.basename(w))]
done = 0
for w in wavs:
    f = os.path.basename(w); text = by.get(f)
    if not text: continue
    W = app.he_words(text)
    if len(W) < 4: continue
    x = app.decode_audio(open(w, 'rb').read())
    try: hlp = head_of(x)
    except Exception as e: print('fail', f, e, flush=True); continue
    alts = random.sample([t for t in texts if t != W], 5)
    ev = app.order_evidence(hlp, W, app.HEAD_S2I, app.he_read, 0); rv = rival_evidence(hlp, W, alts, app.HEAD_S2I, app.he_read)
    rows.append({'set': 'israeli', 'case': 'right', 'f': f, 'gap': ev['gap'], 'rival': rv and rv['gain'], 'n_alts': 5})
    Wo = random.choice([t for t in texts if t != W and abs(len(t) - len(W)) <= 3])
    ev2 = app.order_evidence(hlp, Wo, app.HEAD_S2I, app.he_read, 0); rv2 = rival_evidence(hlp, Wo, alts[:4] + [W], app.HEAD_S2I, app.he_read)
    rows.append({'set': 'israeli', 'case': 'wrongline', 'f': f, 'gap': ev2['gap'], 'rival': rv2 and rv2['gain'], 'n_alts': 5})
    done += 1
    if done >= NI: break
json.dump(rows, open(os.path.join(HERE, 'calib_rival.json'), 'w'), ensure_ascii=False)
print(f'done: {len(rows)} rows, {int(time.time() - t_start)} s')
for s in ('alouf', 'israeli'):
    for case in ('right', 'wrongline'):
        g = [r['gap'] for r in rows if r['set'] == s and r['case'] == case and r['gap'] is not None]; rv = [r['rival'] for r in rows if r['set'] == s and r['case'] == case and r['rival'] is not None]
        if not g: continue
        print(f"{s:8s} {case:9s} n={len(g):3d}  gap p05/p50/p95/max {np.percentile(g, 5):.2f}/{np.percentile(g, 50):.2f}/{np.percentile(g, 95):.2f}/{max(g):.2f}   rival gain p05/p50/p95 min/max {np.percentile(rv, 5):.3f}/{np.percentile(rv, 50):.3f}/{np.percentile(rv, 95):.3f} {min(rv):.3f}/{max(rv):.3f}")
