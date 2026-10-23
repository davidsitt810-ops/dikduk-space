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
# the offline rule, as exam_rules.py has it
exec(open(os.path.join(HERE, 'exam_rules.py')).read().split('# group rows by line')[0].split("print(f'{len(R)} word rows")[0].replace("R = json.load", "R = []; _ = json.load") if False else '', {})
def mark_old(r, clean):
    n = r.get('n') or 0; sk = r.get('skel'); ft = r.get('_fit'); kp = r.get('kept'); pw = r.get('pw'); hs = r.get('hskel')
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
def offline(res):
    TW = res['take']['words']; F = res.get('fit')
    for i, t in enumerate(TW): t['_fit'] = F[i].get('fit') if F else None
    hs = sorted(t['hskel'] for t in TW if (t.get('n') or 0) >= 2 and t.get('hskel') is not None); clean = bool(hs) and hs[len(hs) // 2] >= .7
    marks = [mark_old(t, clean) for t in TW]
    if clean:
        ds = [t['drop'] if t.get('drop') is not None else -1e9 for t in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
        if (TW[top]['n'] or 0) >= 2 and ds[top] >= 10 and ds[top] - second >= 4: marks[top] = 'off'
        sw = [t['swap'] if t.get('swap') is not None else -1e9 for t in TW[:-1]]
        if sw:
            j = int(np.argmax(sw))
            na, nb = (TW[j]['n'] or 0), (TW[j + 1]['n'] or 0)
            if sw[j] >= 8 and max(na, nb) >= 2 and min(na, nb) >= 1: marks[j] = marks[j + 1] = 'off'
        if res['take'].get('gap') is not None and res['take']['gap'] >= 0.6: marks = ['unsure' if m == 'ok' else m for m in marks]
    return marks
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
