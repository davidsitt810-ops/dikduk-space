"""End-to-end test of the letter checker against a running server (default http://127.0.0.1:7861):
1. every example snippet in static/letters.json, posted as the student's take for its own letter -> should be right
   (they were chosen because the checker hears them right; this checks the whole route: mp3 in, trim, probe, verdict);
2. a few Israeli word cuts (FLEURS) for ע ח ק ת -> ע ח ק wrong or unsure, never right; ת right or unsure;
3. odd inputs: silence, a tone, a tiny body, a letter the checker does not know, strict mode on an unsure take.
usage: t_letters.py [base url]"""
import sys, os, json, glob, io, wave, struct, math, random
import requests, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861'
SPACE = os.path.join(HERE, '..', 'space')
fails = []
def post(data, c, want=None, strict=0):
    q = {'c': c}
    if want: q['want'] = want
    if strict: q['strict'] = 1
    r = requests.post(BASE + '/letter', params=q, data=data, headers={'Content-Type': 'application/octet-stream'}, timeout=120)
    return r.status_code, r.json()
# 1. the examples
J = json.load(open(os.path.join(SPACE, 'static', 'letters.json'), encoding='utf-8'))
n = 0; ok = 0; unsure = 0
for L in J['letters']:
    for want, exs in L['examples'].items():
        for e in exs:
            data = open(os.path.join(SPACE, 'static', 'letters', e['audio']), 'rb').read()
            st, j = post(data, L['c'], want or None)
            n += 1
            if st != 200: fails.append(('example status', L['c'], want, e['audio'], st, j)); continue
            if j['v'] == 'right': ok += 1
            elif j['v'] == 'unsure': unsure += 1
            else: fails.append(('example not right', L['c'], want, e['pointed'], j['v'], j.get('say'), j.get('why')))
            for k in ('v', 'say', 'more', 'heard', 'peak', 'ar_peak', 'win', 'dur', 'ms', 'c'):
                if k not in j: fails.append(('missing key', k, e['audio']))
print(f'examples: {n} posted, right {ok}, unsure {unsure}, wrong {n - ok - unsure}')
# 2. Israeli cuts
rows = [r for r in json.load(open(os.path.join(HERE, 'letters_rows.json'), encoding='utf-8')) if r['src'] == 'il' and r['c'] in 'עחקת' and r.get('first')]
random.seed(1); random.shuffle(rows)
meta = json.load(open(os.path.join(HERE, '..', 'fleurs', 'dev.json'), encoding='utf-8'))
def wav_bytes(x):
    b = io.BytesIO(); w = wave.open(b, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes()); w.close(); return b.getvalue()
sys.path.insert(0, SPACE); import subprocess
def decode(path):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()
done = {c: 0 for c in 'עחקת'}; res = {c: [] for c in 'עחקת'}
for r in rows:
    if done[r['c']] >= 4: continue
    f = r['f']; p = next((q for q in [os.path.join(HERE, '..', 'fleurs_fresh', 'dev', f), os.path.join(HERE, '..', 'fleurs', 'dev', f)] if os.path.exists(q)), None)
    if not p: continue
    x = decode(p); xs = x[int(max(0, r['t0'] - 0.05) * 16000):int((r['t1'] + 0.05) * 16000)]
    st, j = post(wav_bytes(xs), r['c']); done[r['c']] += 1; res[r['c']].append(j['v'])
    if st != 200: fails.append(('israeli status', r['c'], st, j)); continue
    if r['c'] in 'עחק' and j['v'] == 'right': fails.append(('israeli called right', r['c'], r['w'], j.get('why')))
    if r['c'] == 'ת' and j['v'] == 'wrong': fails.append(('israeli tav called wrong', r['w'], j.get('why')))
print('israeli word-initial takes:', {c: v for c, v in res.items()})
# 3. odd inputs
sr = 16000
st, j = post(wav_bytes(np.zeros(sr * 2, dtype=np.float32)), 'ע'); print('silence:', st, j.get('v'), j.get('say'))
if not (st == 200 and j.get('v') == 'no_speech'): fails.append(('silence', st, j.get('v')))
tone = (0.3 * np.sin(2 * np.pi * 440 * np.arange(sr * 2) / sr)).astype(np.float32)
st, j = post(wav_bytes(tone), 'ח'); print('tone:', st, j.get('v'), j.get('say'))
if st != 200 or j.get('v') == 'right': fails.append(('tone', st, j.get('v')))
st, j = post(b'xx', 'ע'); print('tiny body:', st, j)
if st != 400: fails.append(('tiny body', st))
st, j = post(wav_bytes(tone), 'ג'); print('unknown letter:', st, j)
if st != 400: fails.append(('unknown letter', st))
st, j = post(wav_bytes(tone), 'ב', 'v'); print('want v:', st, j.get('v'), j.get('say'))
st, j = post(wav_bytes(tone), 'ב', 'zz'); print('bad want:', st, j.get('v'), j.get('say'))
if st != 200: fails.append(('bad want', st))
st, j = post(wav_bytes(tone), 'ח', strict=1); print('strict on a tone:', st, j.get('v'), j.get('say'))
if st == 200 and j.get('v') == 'unsure': fails.append(('strict left unsure', j))
# the page and the data
for path, must in (('/letters', '<script>'), ('/letters.json', '"letters"'), ('/letters/audio/ayin-1.mp3', None), ('/health', '"letters"')):
    r = requests.get(BASE + path, timeout=30, allow_redirects=False)
    if r.status_code not in (200, 307) or (must and must not in r.text): fails.append(('route', path, r.status_code))
    else: print('route ok', path, r.status_code, len(r.content))
print('\nFAILS:' if fails else '\nall good', *fails, sep='\n  ')
sys.exit(1 if fails else 0)
