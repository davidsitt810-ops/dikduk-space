"""The letter checker's study: word-initial letters cut out as a student would record them (one short word), through
app.letter_probe — Rabbi Alouf's Tehillim (the Sephardic sounds; the nikud gives the dagesh / shin-sin variant) and
Israelis reading (FLEURS dev + fresh: ע said as alef, ח as khaf, ק as kaf, ט as tav, צ as ts, ר from the back).
Writes letters_rows.json: one row per cut with every ear's numbers; letters_rules.py reads it.
usage: letters_study.py [per-letter cap for Alouf=120] [fleurs sentences=199]      env: STUDY_OUT, SKIP_IL=1, SKIP_AL=1"""
import sys, os, json, glob, time, random, subprocess, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app
from nikud import parse_verse
HERE = os.path.dirname(os.path.abspath(__file__)); random.seed(11)
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 120; NI = int(sys.argv[2]) if len(sys.argv) > 2 else 199
OUT = os.path.join(HERE, os.environ.get('STUDY_OUT', 'letters_rows') + '.json')
TARGET = set(os.environ.get('LETTERS', 'עחאקטצרבכפשתהסדגזלמנ'))
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
MP3 = os.path.join(HERE, '..', 'alouf', 'mp3')

def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(MP3, fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()

def variant(units, c):
    """the asked-for variant of a word-initial letter from its nikud units: b/v k/kh p/f sh/s, t/t(dagesh), else None"""
    u = units[0] if units else None
    if not u or u['kind'] != 'cons' or u['c'] != c: return 'skip'
    if c == 'ב': return 'b' if u['dagesh'] else 'v'
    if c == 'כ': return 'k' if u['dagesh'] else 'kh'
    if c == 'פ': return 'p' if u['dagesh'] else 'f'
    if c == 'ש': return 's' if u['alts'] == ['s'] else 'sh'
    if c == 'ת': return 'dagesh' if u['dagesh'] else 'rafe'
    return None

rows = []
if os.path.exists(OUT) and os.environ.get('RESUME'):
    rows = json.load(open(OUT, encoding='utf-8')); print('resuming with', len(rows), 'rows', flush=True)
done = set((r['src'], r['id']) for r in rows)
t_start = time.time()

def save():
    json.dump(rows, open(OUT, 'w'), ensure_ascii=False)

def probe_row(x, c, meta):
    try: P = app.letter_probe(x, c)
    except Exception as e: print('probe fail', meta.get('id'), e, flush=True); return
    r = dict(meta); r['c'] = c
    for k in ('dur', 'cut', 'no_speech', 'onset', 'win', 'heard', 'peak', 'ar_peak', 'ar_mass', 'head_mass', 'head_peak', 'throat', 'ms'):
        if k in P: r[k] = P[k]
    r['phones'] = [(s['p'], s['t'], s['c']) for s in P.get('phones', [])[:8]]
    r['arabic'] = [(s['p'], s['t'], s['c']) for s in P.get('arabic', [])[:6]]
    rows.append(r)

# ---------------------------------------------------------------- Rabbi Alouf
if not os.environ.get('SKIP_AL'):
    cands = collections.defaultdict(list)
    for n, rec in IDX['perakim'].items():
        if not os.path.exists(os.path.join(MP3, rec['original'])): continue
        for i, p in enumerate(rec['pesukim']):
            if p.get('t0') is None or not p.get('nikud') or not p.get('words'): continue
            try: V = parse_verse(p['nikud'])
            except Exception: continue
            if len(V) != len(p['words']): continue
            for j, w in enumerate(p['words']):
                hl = app.he_letters(w['w']); pointed, letters, units = V[j]
                if not hl or letters != hl or hl[0] not in TARGET: continue
                if w.get('fit') is None or w['fit'] < .6 or w.get('t0') is None or w.get('t1') is None: continue
                d = w['t1'] - w['t0']
                if not (.3 <= d <= 1.6): continue
                var = variant(units, hl[0])
                if var == 'skip': continue
                vow = next((u['c'] for u in units if u['kind'] == 'vowel'), None)
                cands[hl[0]].append({'id': f'{n}_{i}_{j}', 'per': int(n), 'ps': i, 'k': j, 'w': w['w'], 'pointed': pointed, 'var': var, 'vow': vow, 'fit': w['fit'], 'rec': rec['original'], 't0': w['t0'], 't1': w['t1'], 'next': (app.he_letters(p['words'][j + 1]['w'])[:1] if j + 1 < len(p['words']) else '')})
    print('alouf candidates:', {c: len(v) for c, v in sorted(cands.items())}, flush=True)
    for c in sorted(cands):
        L = cands[c]; random.shuffle(L)
        # the variants of a letter each get their share
        byv = collections.defaultdict(list)
        for m in L: byv[m['var']].append(m)
        take = []
        for v, ms in byv.items(): take += ms[:CAP]
        for m in take:
            if ('al', m['id']) in done: continue
            x = cut(m['rec'], m['t0'] - 0.1, m['t1'] + 0.1)
            if x.shape[0] < app.SR * 0.2: continue
            probe_row(x, c, {'src': 'al', **m})
        print(f'alouf {c}: {len(take)} cuts · {len(rows)} rows · {int(time.time() - t_start)} s', flush=True); save()

# ---------------------------------------------------------------- Israelis reading (FLEURS)
if not os.environ.get('SKIP_IL'):
    meta = json.load(open(os.path.join(HERE, '..', 'fleurs', 'dev.json'), encoding='utf-8')); by = {r[1]: r[3] for r in meta}
    wavs = sorted(glob.glob(os.path.join(HERE, '..', 'fleurs_fresh', 'dev', '*.wav'))) + sorted(glob.glob(os.path.join(HERE, '..', 'fleurs', 'dev', '*.wav')))
    n_s = 0
    for wv in wavs:
        f = os.path.basename(wv); text = by.get(f)
        if not text: continue
        W = app.he_words(text)
        if len(W) < 3: continue
        x = app.decode_audio(open(wv, 'rb').read())
        try:
            lp, spf, H = app.run_model(x); PW = app.place_words(lp, spf, W)
        except Exception as e: print('place fail', f, e, flush=True); continue
        for j, w in enumerate(PW):
            hl = app.he_letters(w['w'])
            if not hl or hl[0] not in TARGET or (w['n'] or 0) < 1 or (w['skel'] or 0) < .35: continue
            if j > 0:
                prev = app.he_letters(PW[j - 1]['w'])
                if prev[-1:] in 'אהוי' and hl[0] in 'אעה': continue   # the cut would hold the previous word's vowel
            d = w['t1'] - w['t0']
            if not (.25 <= d <= 1.8): continue
            a = w['t0'] - (0.05 if j > 0 else 0.0); b = w['t1'] + 0.05
            xs = x[int(max(0, a) * app.SR):int(b * app.SR)]
            if xs.shape[0] < app.SR * 0.2: continue
            m = {'id': f'{f}_{j}', 'f': f, 'k': j, 'w': w['w'], 'pointed': None, 'var': None, 'vow': None, 'fit': w['skel'], 't0': w['t0'], 't1': w['t1'], 'next': (app.he_letters(PW[j + 1]['w'])[:1] if j + 1 < len(PW) else ''), 'first': j == 0}
            if ('il', m['id']) in done: continue
            probe_row(xs, hl[0], {'src': 'il', **m})
        n_s += 1
        if n_s % 20 == 0: print(f'israeli {n_s} sentences · {len(rows)} rows · {int(time.time() - t_start)} s', flush=True); save()
        if n_s >= NI: break
    save()
print('done', len(rows), 'rows', int(time.time() - t_start), 's')
print(collections.Counter((r['src'], r['c']) for r in rows))
