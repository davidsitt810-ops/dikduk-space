"""Odd inputs through the local server's /check: silence, a very short take, a long take, noise, a single word, words
with maqaf/punctuation, a pasuk with nikud, an unknown reference file, an empty body, a bad mime. The server must
answer (a result or a clear error), never a 500 or a hang."""
import json, io, wave, sys, time, requests, numpy as np
B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861'; SR = 16000
def wav(y):
    b = io.BytesIO(); w = wave.open(b, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); w.close(); return b.getvalue()
rng = np.random.default_rng(0)
take = open('take_alouf_23_1.wav', 'rb').read()
cases = [
    ('silence 3 s', {'words': 'מזמור לדוד יי רעי לא אחסר'}, wav(np.zeros(3 * SR))),
    ('0.2 s', {'words': 'מזמור לדוד יי רעי לא אחסר'}, wav(np.zeros(int(.2 * SR)))),
    ('noise 4 s', {'words': 'מזמור לדוד יי רעי לא אחסר'}, wav(rng.normal(0, .1, 4 * SR))),
    ('long 70 s quiet noise', {'words': 'מזמור לדוד יי רעי לא אחסר'}, wav(rng.normal(0, .01, 70 * SR))),
    ('one word', {'words': 'מזמור'}, take),
    ('maqaf and punctuation', {'words': 'מזמור לְדָוִד, יי־רֹעִי לֹא אֶחְסָר׃'}, take),
    ('latin letters', {'words': 'hello world'}, take),
    ('empty words', {'words': ''}, take),
    ('many words', {'words': ' '.join(['מזמור'] * 40)}, take),
    ('with nikud param', {'words': 'מזמור לדוד יי רעי לא אחסר', 'nikud': 'מִזְמ֥וֹר לְדָוִ֑ד יְהֹוָ֥ה רֹ֝עִ֗י לֹ֣א אֶחְסָֽר'}, take),
    ('unknown ref file', {'words': 'מזמור לדוד יי רעי לא אחסר', 'ref': 'no-such-file.mp3', 't0': 0, 't1': 5}, take),
    ('tehillim ref', {'words': 'מזמור לדוד יי רעי לא אחסר', 'ref': 'tehillim-023.mp3', 't0': 0.2, 't1': 5.9}, take),
    ('ref with t1 < t0', {'words': 'מזמור לדוד יי רעי לא אחסר', 'ref': 'tehillim-023.mp3', 't0': 5, 't1': 2}, take),
    ('empty body', {'words': 'מזמור לדוד יי רעי לא אחסר'}, b''),
    ('garbage bytes', {'words': 'מזמור לדוד יי רעי לא אחסר'}, b'\x00\x01\x02garbage' * 100),
]
for name, params, body in cases:
    t = time.time()
    try:
        r = requests.post(B + '/check', params=params, data=body, headers={'Content-Type': 'audio/wav'}, timeout=300)
        try: j = r.json()
        except Exception: j = {'raw': r.text[:100]}
        words = j.get('take', {}).get('words') if isinstance(j, dict) else None
        print(f"{name:26s} HTTP {r.status_code} {time.time() - t:5.1f}s  " + (f"words {len(words)} marks-ready err={j.get('err')!r} ref_err={str(j.get('ref_err'))[:60]!r}" if words is not None else f"-> {str(j)[:140]}"))
    except Exception as e:
        print(f"{name:26s} EXC {e}")
# the job path
r = requests.post(B + '/check', params={'words': 'מזמור לדוד יי רעי לא אחסר', 'job': 1}, data=take, headers={'Content-Type': 'audio/wav'}, timeout=60).json(); print('job:', r)
for _ in range(60):
    s = requests.get(B + '/job/' + r['job']).json()
    if s.get('state') in ('done', 'error'): break
    time.sleep(2)
print('job state', s.get('state'), 'stage', s.get('stage'), 'words', len((s.get('result') or {}).get('take', {}).get('words', [])))
print('unknown job:', requests.get(B + '/job/nope').status_code)
