"""Does the server's own verdict (summarize/marks_of) agree with the exam's offline rule? Six held-out pesukim,
tampered as in exam_alouf.py, submitted through /submit; the stored summary.marks are compared with the rule applied
to the stored result. Also the live swap/skip/wrong-line headlines."""
import json, os, sys, subprocess, random, time, wave, io, requests, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__)); B = 'http://127.0.0.1:7861'
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
PER = [7, 12, 18, 21, 23, 32, 35, 40, 46, 94, 118, 123, 126, 140]; random.seed(11); SR = 16000
def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(HERE, '..', 'alouf', 'mp3', fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()
def wav_bytes(y):
    b = io.BytesIO(); w = wave.open(b, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); w.close(); return b.getvalue()
jobs = []
for n in PER:
    rec = IDX['perakim'][str(n)]
    for i, p in enumerate(rec['pesukim']):
        if p['t0'] is None or p['t1'] - p['t0'] > 12 or len(p['words']) < 5 or any(w['t0'] is None for w in p['words']): continue
        jobs.append((n, rec, i))
random.shuffle(jobs); jobs = jobs[:6]
# the offline rule: app.py's own functions, as exam_report.py extracts them (so this checks the server's wiring —
# analyse -> summarize -> stored summary — not a second copy of the rule)
import importlib.util
_spec = importlib.util.spec_from_file_location('exam_report', os.path.join(HERE, 'exam_report.py')); _er = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_er)
def offline(res):
    TW = res['take']['words']; F = res.get('fit')
    for i, t in enumerate(TW): t['fit'] = F[i].get('fit') if F else None
    marks, why, lw, cant, clean = _er.live_marks(TW); return marks
agree = 0; total = 0; heads = collections.Counter(); ids = []
for n, rec, i in jobs:
    p = rec['pesukim'][i]; off = p['t0'] - .2; x = cut(rec['original'], off, p['t1'] + .2); W = [w.get('said', w['w']) for w in p['words']]; wt = [(w['t0'], w['t1']) for w in p['words']]
    seg = lambda a, b: x[int((a - off) * SR):int((b - off) * SR)]
    cases = {'right': x}
    j = random.choice([k for k in range(1, len(W) - 1)]); cases['skip'] = np.concatenate([seg(off, wt[j][0]), seg(wt[j][1], p['t1'] + .2)]); skipw = W[j]
    j = random.choice([k for k in range(0, len(W) - 1) if wt[k][1] <= wt[k + 1][0] + 1e-3] or [0]); (a1, b1), (a2, b2) = wt[j], wt[j + 1]
    cases['swap'] = np.concatenate([seg(off, a1), seg(a2, b2), seg(b1, a2), seg(a1, b1), seg(b2, p['t1'] + .2)]); swapw = (W[j], W[j + 1])
    for do, y in cases.items():
        labels = {'word': skipw} if do == 'skip' else ({'pair': list(swapw)} if do == 'swap' else {})
        meta = {'set': 'test', 'task': f'{n}-{i}-{do}', 'name': 'tmarks', 'who': 'tmarks', 'text': f't{n}:{i + 1}', 'do': do, 'labels': labels, 'mime': 'audio/wav', 'check': True}
        r = requests.post(B + '/submit', params={'meta': json.dumps(meta, ensure_ascii=False)}, data=wav_bytes(y), timeout=120).json(); ids.append((r['id'], do, n, i))
# wait for grading, then compare
for _ in range(120):
    J = [requests.get(B + f'/takes/full/{tid}').json() for tid, *_ in ids]
    if all(j.get('graded') for j in J): break
    time.sleep(3)
for (tid, do, n, i), j in zip(ids, J):
    if not j.get('summary'): print('no summary', tid, j.get('error')); continue
    srv = j['summary']['marks']; off_ = offline(j['result']); total += 1; agree += (srv == off_)
    if srv != off_: print('DISAGREE', do, n, i + 1, 'server', srv, 'offline', off_)
    heads[(do, 'line_wrong' if j['summary'].get('line_wrong') else ('swapped' if 'swapped' in (j['summary'].get('why') or []) else ('red' if 'off' in srv else ('unsure' if 'unsure' in srv else 'clean'))))] += 1
print(f'server marks == offline rule on {agree}/{total} takes'); print('headlines by case:', dict(heads))
S = requests.get(B + '/score', params={'set': 'test', 'who': 'tmarks'}).json(); print('scoreboard totals:', S['totals'])
