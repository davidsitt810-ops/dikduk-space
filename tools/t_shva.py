"""End to end: the shva check through POST /check on a running server (default http://127.0.0.1:7861).
1. Rabbi Alouf's Tehillim 23:2 against his own recording: every sheva heard, no note.
2. The same take with the short vowel of מְ in מְנֻחוֹת cut out: a "say a short e" note on that word (and on nothing else).
3. The same take with a short vowel put into the silent shva of יַרְבִּיצֵנִי: a "no vowel" note there.
4. Without nikud (a pizmon line): no shva fields at all.
usage: t_shva.py [base url]"""
import sys, os, io, json, wave
import numpy as np, requests
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:7861'
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
P = IDX['perakim']['23']['pesukim'][1]; NIK = P['nikud']; WORDS = P['text']
fails = []
def wav_bytes(x):
    b = io.BytesIO(); w = wave.open(b, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes()); w.close(); return b.getvalue()
def read_wav(p):
    with wave.open(p, 'rb') as w: return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32768
def check(x, nikud=NIK, ref=True):
    q = {'words': WORDS}
    if nikud: q['nikud'] = nikud
    if ref: q.update(ref='tehillim-023.mp3', t0=P['t0'], t1=P['t1'])
    r = requests.post(BASE + '/check', params=q, data=wav_bytes(x), headers={'Content-Type': 'application/octet-stream'}, timeout=300)
    j = r.json()
    if r.status_code != 200: fails.append(('status', r.status_code, j)); return {}
    return j
XF = 64
def splice(a, b):
    w = np.linspace(0, 1, XF, dtype=np.float32)
    return np.concatenate([a[:-XF], a[-XF:] * (1 - w) + b[:XF] * w, b[XF:]])
x = read_wav(os.path.join(HERE, 'take_alouf_23_2.wav'))
# 1. intact
j = check(x); spf = j['take']['spf']; SH = j.get('shva_heard') or {}
print('intact: shvas', {i: [(s['c'], s['rule'], s['heard']) for s in v] for i, v in SH.items()}, '| notes', j.get('shva'), '| hazzan', bool((j.get('ref') or {}).get('shva')))
if not SH: fails.append('no shva_heard')
if j.get('shva'): fails.append(('notes on his own reading', j['shva']))
if not (j.get('ref') or {}).get('shva'): fails.append('the hazzan has no shva analysis')
W = j['words']; mi = next(i for i, w in enumerate(W) if w.startswith('מנח')); yi = next(i for i, w in enumerate(W) if w.startswith('ירב'))
m = next((s for s in SH.get(str(mi), []) if s['k'] == 0), None); y = next((s for s in SH.get(str(yi), []) if s['rule'] == 'short'), None)
print('  מְנֻחוֹת:', m and (m['heard'], m['mass']), '| יַרְבִּיצֵנִי:', y and (y['heard'], y['gapmax_any']))
# 2. drop a shva na's vowel (each start-shva of the pasuk in turn): the whole stretch between the two consonants is
#    cut (keeping 20 ms at each end). Plumbing: wherever the server now hears 'none' there, a note must say so; and no
#    note may land elsewhere. (How often the cut is heard at all is shva_eval.py's question: about half.)
caught = 0; tried = 0
for wi, slots in SH.items():
    for s0 in slots:
        if s0['rule'] != 'start' or s0['heard'] != 'vowel' or s0['g0'] < 0 or s0['g1'] - s0['g0'] < 3: continue
        a = int((s0['g0'] + 1) * spf * 16000); b = int((s0['g1'] - 1) * spf * 16000); tried += 1
        j2 = check(splice(x[:a], x[b:])); n2 = j2.get('shva') or {}; h2 = next((q for q in (j2.get('shva_heard') or {}).get(wi, []) if q['k'] == s0['k']), None)
        hit = any(d['k'] == s0['k'] and d['want'] == 'vowel' and d['you'] == 'none' for d in n2.get(wi, []))
        print(f"drop in {W[int(wi)]}: heard {h2 and h2['heard']} (e-mass {h2 and h2['mass']}, any-vowel {h2 and h2['gapmax_any']}) -> note {hit}")
        caught += hit
        if h2 and h2['heard'] == 'none' and not hit: fails.append(('heard none but no note', wi, n2))
        if any(k != wi for k in n2): fails.append(('collateral notes', n2))
print(f'  dropped shva na caught {caught}/{tried}')
if not tried: fails.append('no start shva to cut')
# 3. a vowel added into the silent shva of יַרְבִּיצֵנִי (his own vowel, from מְ)
if y and y['heard'] == 'none' and m:
    a = int(m['f0'] * spf * 16000); b = int(m['f1'] * spf * 16000); mid = (a + b) // 2; snip = x[max(0, mid - 600):mid + 600]
    at = int((y['g0'] + y['g1']) / 2 * spf * 16000)
    j3 = check(splice(splice(x[:at], snip), x[at:])); n3 = j3.get('shva') or {}
    print('add:', n3)
    if not any(d['want'] == 'none' and d['you'] == 'vowel' for d in n3.get(str(yi), [])): fails.append(('added vowel not caught', n3))
# 4. no nikud: no shva at all
j4 = check(x, nikud=None, ref=False)
print('no nikud: shva fields', [k for k in j4 if k.startswith('shva')])
if any(k.startswith('shva') for k in j4): fails.append('shva fields without nikud')
print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
