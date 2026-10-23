"""David's blind test: a folder of his recordings + a manifest saying which text each one claims to be; every
recording goes through the checker exactly as the page would send it (words, nikud for Tehillim, the hazzan's
reference line and its times), and the report says in plain words what the machine claims about each — the same
sentences the page shows — plus the verdict on every ayin/het and the vowel differences. David scores the claims
against what he actually did; nothing here knows his answer key.

manifest.txt: one recording per line:   <file>  <text>  [anything after is a note shown in the report]
   text = t23:1 (Tehillim perek:pasuk)  |  200:3 (pizmon:line)  |  "Hebrew words" (no hazzan to compare with)
usage: blind_test.py <folder> [server=http://127.0.0.1:7861]       writes <folder>/report.md and results.json
"""
import sys, os, re, json, time, shlex, statistics, requests
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
FOLDER = sys.argv[1]; SRV = (sys.argv[2] if len(sys.argv) > 2 else 'http://127.0.0.1:7861').rstrip('/')
LYP = json.load(open(os.path.join(ROOT, 'lyrics_full.json'), encoding='utf-8'))['s']
LYT = json.load(open(os.path.join(ROOT, 'space', 'lyrics_tehillim.json'), encoding='utf-8'))['s']
HEALTH = requests.get(SRV + '/health', timeout=120).json()
HAVE = set(HEALTH.get('ears', {}).get('tehillim_perakim') or [1, 23, 117, 121, 130, 133, 134, 150])
PHR = {"md cd08 15.mp3": [[0.35, 6.9, 0], [7.4, 14, 1], [20.75, 27.7, 2], [28.1, 34.35, 3], [41.4, 50.25, 4], [50.5, 55.25, 5], [55.7, 61.35, 6], [61.85, 66.5, 7]]}

def sync_lines(s, f):
    """line k -> (t0, t1) from the recording's sync events, as the page computes them"""
    if f in PHR: return {k: (a, b) for a, b, k in PHR[f]}
    ev = [tuple(map(int, x.split(','))) for x in (s.get('t', {}).get(f) or '').split(';') if x]; out = {}
    for i, (t, k) in enumerate(ev):
        if k < 0 or k in out: continue
        out[k] = (t / 10, ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8)
    return out

def resolve(spec):
    """what the recording claims to be -> the /check parameters and a label"""
    m = re.fullmatch(r't(\d+):(\d+)', spec)
    if m:
        n, k = int(m.group(1)), int(m.group(2)) - 1; s = LYT.get(f't{n}')
        if not s or k >= len(s['l']): raise ValueError(f'no Tehillim {n}:{k + 1}')
        p = {'words': s['l'][k], 'nikud': s['ln'][k]}; f = f'tehillim-{n:03d}.mp3'
        if n in HAVE and f in (s.get('t') or {}):
            L = sync_lines(s, f)
            if k in L: p.update({'ref': f, 't0': L[k][0], 't1': L[k][1]})
        return p, f'Tehillim {n}:{k + 1}', s['l'][k]
    m = re.fullmatch(r'(\d+):(\d+)', spec)
    if m:
        pid, k = m.group(1), int(m.group(2)) - 1; s = LYP.get(pid)
        if not s or k >= len(s['l']): raise ValueError(f'no pizmon {pid} line {k + 1}')
        p = {'words': s['l'][k]}; recs = list((s.get('t') or {}).keys()); b = s.get('b') if s.get('b') in recs else (recs[0] if recs else None)
        if b:
            L = sync_lines(s, b)
            if k in L: p.update({'ref': b, 't0': L[k][0], 't1': L[k][1]})
        return p, f'pizmon {pid} line {k + 1}', s['l'][k]
    return {'words': spec}, 'words', spec

def mark_of(y, f, clean):
    """the page's rule, word by word"""
    n = y.get('n') or 0; sk = y.get('skel'); ft = f.get('fit') if f else None
    if not n or sk is None: return ''
    kp = y.get('kept'); pw = y.get('pw')
    if n >= 2:
        if sk < .2 and (ft is None or ft < .15): return 'off'
        if clean and pw is not None and pw >= .95: return 'off'
        if sk < .4 or (ft is not None and ft < .2) or (kp is not None and kp < .5) or (pw is not None and pw >= .8): return 'unsure'
        return 'ok'
    return 'unsure' if sk < .2 else 'ok'

def describe(j):
    """the page's sentences for one check: headline, per-word notes, throat verdicts, vowel differences, marks"""
    W, TW, F = j['words'], j['take']['words'], j.get('fit')
    hs = sorted(t['hskel'] for t in TW if (t.get('n') or 0) >= 2 and t.get('hskel') is not None)
    clean = bool(hs) and hs[len(hs) // 2] >= .7
    marks = [mark_of(TW[i], F[i] if F else None, clean) for i in range(len(W))]
    VN = j.get('vowel_names') or {}; vname = lambda k: (VN.get(k) or k).split(' ')[0]
    notes = []; throat = []
    for i, w in enumerate(W):
        t = TW[i]; parts = []
        if marks[i] == 'off': parts.append('not heard where it belongs')
        elif marks[i] == 'unsure': parts.append('not sure it was there')
        if marks[i] != 'ok' and t.get('miss') and len(t['miss']) < (t.get('n') or 9): parts.append(' '.join(t['miss']) + ' not heard')
        for th in t.get('throat') or []:
            throat.append((th['c'], w, th.get('v')))
            if th.get('v') == 'plain': parts.append('the ע was said like alef' if th['c'] == 'ע' else 'the ח was not from the throat')
        for nn in t.get('notes') or []:
            if nn.get('say') == 'sav': parts.append('the ת sounded like a samekh')
        vd = (j.get('vowels') or {}).get(str(i)) or (j.get('vowels') or {}).get(i) or []
        vn = (j.get('vowels_nikud') or {}).get(str(i)) or (j.get('vowels_nikud') or {}).get(i) or []
        for d in vd: parts.append(f"you sang {vname(d['you'])} where the hazzan sings {vname(d['ref'])}")
        for d in vn:
            if not any(x['k'] == d['k'] for x in vd): parts.append(f"you sang {vname(d['you'])} where the nikud says {vname(d['ref'])}")
        if parts: notes.append(f'{w}: ' + '; '.join(parts) + '.')
    off = [W[i] for i, m in enumerate(marks) if m == 'off']; uns = [W[i] for i, m in enumerate(marks) if m == 'unsure']
    if not F and j.get('ref_err') and 'Tehillim' not in j['ref_err']: head = 'No hazzan recording to compare with, so only the consonants were checked.'
    elif not notes: head = 'Every word came through as the hazzan sings it.' if F else 'Every word came through.'
    elif off: head = f'{len(W) - len(off)} of {len(W)} words came through. Not heard: {", ".join(off)}' + (f'. Not sure: {", ".join(uns)}' if uns else '') + '.'
    elif uns: head = f'The words are there; not sure about {", ".join(uns)}.'
    else: head = 'The words are there, with a few things to hear.'
    return {'head': head, 'notes': notes, 'throat': throat, 'marks': marks, 'clean': clean}

TH = {'throat': 'from the throat ✓', 'plain': 'said plain ✕', 'unsure': 'not sure', None: '?'}
rows = []; md = [f'# Blind test — {time.strftime("%Y-%m-%d %H:%M")} — server {SRV} (v{HEALTH.get("version")})', '',
                 'For each recording: what it claims to be, then everything the machine says about it. Score every claim against what you actually did.', '']
for line in open(os.path.join(FOLDER, 'manifest.txt'), encoding='utf-8'):
    line = line.strip()
    if not line or line.startswith('#'): continue
    parts = shlex.split(line); fname, spec = parts[0], parts[1]; note = ' '.join(parts[2:])
    path = os.path.join(FOLDER, fname)
    try:
        params, label, text = resolve(spec)
        if not os.path.exists(path): raise FileNotFoundError(fname)
        t = time.time(); r = requests.post(SRV + '/check', params=params, data=open(path, 'rb').read(), timeout=900); j = r.json()
        if 'err' in j: raise RuntimeError(j['err'])
        d = describe(j); secs = time.time() - t
    except Exception as e:
        md += [f'## {fname} — {spec}', '', f'**could not check:** {e}', '']; rows.append({'file': fname, 'spec': spec, 'error': str(e)}); continue
    W, TW, F = j['words'], j['take']['words'], j.get('fit')
    md += [f'## {fname} — {label}' + (f' — *{note}*' if note else ''), '', f'<div dir="rtl">{text}</div>', '',
           f'**{d["head"]}**', '']
    md += [f'- {n}' for n in d['notes']] or ['- (nothing to say about any word)']
    if d['throat']: md += ['', 'Throat letters: ' + ' · '.join(f'{c} in {w}: {TH.get(v, v)}' for c, w, v in d['throat'])]
    md += ['', 'Words: ' + ' · '.join(f'{w} {m or "–"}' for w, m in zip(W, d['marks'])) + (f' · hazzan: {"yes" if j.get("ref") else "no"}' + (f' ({j["ref_err"][:60]})' if j.get('ref_err') else '')) + f' · clean take: {"yes" if d["clean"] else "no"} · {j["take"]["dur"]:.1f} s audio, {secs:.0f} s to check', '']
    md += ['<details><summary>numbers</summary>', '', '| word | cons | fit | head | kept | pw | not heard |', '|---|---|---|---|---|---|---|']
    f2 = lambda x: '–' if x is None else f'{x:.2f}'
    md += [f'| {w} | {f2(t.get("skel"))} | {f2(F[i].get("fit") if F else None)} | {f2(t.get("hskel"))} | {f2(t.get("kept"))} | {f2(t.get("pw"))} | {" ".join(t.get("miss") or [])} |' for i, (w, t) in enumerate(zip(W, TW))]
    md += ['', '</details>', '']
    rows.append({'file': fname, 'spec': spec, 'label': label, 'note': note, 'head': d['head'], 'notes': d['notes'], 'marks': d['marks'], 'throat': d['throat'], 'clean': d['clean'],
                 'words': W, 'skel': [t.get('skel') for t in TW], 'fit': [f.get('fit') for f in F] if F else None, 'hskel': [t.get('hskel') for t in TW], 'kept': [t.get('kept') for t in TW], 'pw': [t.get('pw') for t in TW],
                 'vowels': j.get('vowels'), 'vowels_nikud': j.get('vowels_nikud'), 'throat_full': [t.get('throat') for t in TW], 'dur': j['take']['dur']})
open(os.path.join(FOLDER, 'report.md'), 'w', encoding='utf-8').write('\n'.join(md))
json.dump(rows, open(os.path.join(FOLDER, 'results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n'.join(md))
