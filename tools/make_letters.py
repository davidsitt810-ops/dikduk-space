"""static/letters.json + static/letters/*.mp3: for every letter (and variant) the checker offers, up to six of Rabbi
Alouf's word-initial examples — short words from his Tehillim whose opening letter the checker itself hears as right
(letters_rows.json from letters_study.py, through letters.verdict), cut from the original recordings as second-long
mp3s. usage: make_letters.py [per variant=6]"""
import sys, os, json, subprocess, collections, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
import letters as LT
HERE = os.path.dirname(os.path.abspath(__file__)); N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
SPACE = os.path.join(HERE, '..', 'space'); OUT_DIR = os.path.join(SPACE, 'static', 'letters'); os.makedirs(OUT_DIR, exist_ok=True)
MP3 = os.path.join(HERE, '..', 'alouf', 'mp3')
rows = [r for r in json.load(open(os.path.join(HERE, 'letters_rows.json'), encoding='utf-8')) if r['src'] == 'al']
FIN = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
def hl(w): return ''.join(FIN.get(c, c) for c in re.sub('[֑-ׇ]', '', w) if 'א' <= c <= 'ת')
# a second consonant that would confuse the opening one is avoided in the examples
CONFLICT = {'ע': 'אהח', 'ח': 'הכעא', 'א': 'עהח', 'ק': 'כקג', 'ט': 'תד', 'צ': 'סשזת', 'ר': '', 'ב': 'בפו', 'כ': 'כקחג', 'פ': 'פב', 'ש': 'שסצז', 'ת': 'תטדס'}
SLUG = {'ע': 'ayin', 'ח': 'het', 'א': 'alef', 'ק': 'qof', 'ט': 'tet', 'צ': 'sadi', 'ר': 'resh', 'ב': 'bet', 'כ': 'kaf', 'פ': 'pe', 'ש': 'shin', 'ת': 'tav'}
SHEVA = '\u05b0'
def first_vowel(p):
    p = re.sub('[\u0591-\u05af\u05bd\u05bf\u05c0\u05c4\u05c5]', '', p); m = re.match(r'[\u05d0-\u05ea]([\u05b0-\u05bc\u05c1\u05c2\u05c7]*)', p); marks = m.group(1) if m else ''
    if SHEVA in marks: return 'sheva'
    for ch, cls in [('\u05b7', 'A'), ('\u05b8', 'A'), ('\u05b2', 'A'), ('\u05c7', 'O'), ('\u05b3', 'O'), ('\u05b9', 'O'), ('\u05ba', 'O'), ('\u05b6', 'E'), ('\u05b5', 'E'), ('\u05b1', 'E'), ('\u05b4', 'I'), ('\u05bb', 'U')]:
        if ch in marks: return cls
    if 'ו' in p[1:3]: return 'O'
    return '?'
def want_of(r):
    L = LT.BY_C[r['c']]
    if not L.get('want'): return None
    return r['var']
def margin(r, want):
    L = LT.BY_C[r['c']]
    if L['kind'] in ('throat', 'plain'):
        th = r.get('throat') or {}; votes = th.get('votes') or {}
        key = 'throat' if L['kind'] == 'throat' else 'plain'
        return len(votes.get(key, [])) * 10 + (th.get('ar', {}).get('ع' if r['c'] in 'עא' else 'ح', 0) if L['kind'] == 'throat' else 0)
    if L['kind'] == 'resh': return max(r['ar_peak'].get('ر', 0), r['peak'].get('r', 0)) - r['ar_peak'].get('غ', 0)
    E = LT.EV.get((r['c'], want)) or LT.EV.get((r['c'], None))
    return LT.ev_peak(r, E['for']) - LT.ev_peak(r, E['against'])
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
def medial_examples(c, want, n):
    """Rabbi Alouf says a word-initial ב without dagesh as b (110 of 120), so the vet examples are words with a ב
       inside, after a vowel, where the phone ear hears v (place_words on the word cut)"""
    os.environ.setdefault('DK_NO_WARM', '1'); import app
    from nikud import parse_verse
    import numpy as np
    cands = []
    for per, rec in IDX['perakim'].items():
        if not os.path.exists(os.path.join(MP3, rec['original'])): continue
        for i, p in enumerate(rec['pesukim']):
            if p.get('t0') is None or not p.get('nikud') or not p.get('words'): continue
            try: V = parse_verse(p['nikud'])
            except Exception: continue
            if len(V) != len(p['words']): continue
            for j, w in enumerate(p['words']):
                pointed, letters, units = V[j]
                if not (2 <= len(letters) <= 5) or (w.get('fit') or 0) < .8 or w.get('t0') is None or not (.35 <= w['t1'] - w['t0'] <= 1.3): continue
                cons = [u for u in units if u['kind'] == 'cons']
                for q, u in enumerate(cons):
                    if u['c'] != c or u['k'] == 0 or u['dagesh']: continue
                    prev_vowel = any(v['kind'] == 'vowel' and v['k'] == cons[q - 1]['k'] for v in units) if q else False
                    if not prev_vowel: continue
                    if letters.count(c) > 1: continue
                    cands.append({'w': w['w'], 'pointed': pointed, 'per': int(per), 'ps': i, 'k': u['k'], 'rec': rec['original'], 't0': w['t0'], 't1': w['t1'], 'fit': w['fit']})
    import random; random.seed(5); random.shuffle(cands)
    out = []; seen = set()
    for m in cands:
        if len(out) >= n: break
        if hl(m['w']) in seen: continue
        x = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-ss', f"{max(0, m['t0'] - 0.1):.3f}", '-i', os.path.join(MP3, m['rec']), '-t', f"{m['t1'] - m['t0'] + 0.2:.3f}", '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout, dtype=np.float32).copy()
        if x.shape[0] < 16000 * .3: continue
        lp, spf, H = app.run_model(x); W = app.place_words(lp, spf, [m['w']])
        hit = next((cn for cn in W[0]['cons'] if cn['k'] == m['k']), None)
        if not hit or hit['heard'] != want or hit['mass'].get(want, 0) < 2 * max(hit['mass'].get('b', 0) if want == 'v' else 0, 1e-6) or hit['p'] < .5: continue
        seen.add(hl(m['w'])); out.append(m)
    print(f'  {c} {want}: medial candidates {len(cands)}, heard as {want}: {len(out)}')
    return out
out = {'v': 1, 'made': 'space_test/make_letters.py from letters_rows.json', 'letters': []}
for L in LT.LETTERS:
    c = L['c']; entry = {k: v for k, v in L.items()}; entry['examples'] = {}
    variants = [w[0] for w in L['want']] if L.get('want') else [None]
    for want in variants:
        R = [r for r in rows if r['c'] == c and (want is None or r['var'] == want) and not r.get('no_speech')]
        good = []
        for r in R:
            w = hl(r['w'])
            if not (2 <= len(w) <= 5) or not (.35 <= r['t1'] - r['t0'] <= 1.3) or (r.get('fit') or 0) < .8: continue
            if len(w) > 1 and w[1] in CONFLICT.get(c, ''): continue
            if L['kind'] == 'emphatic' and first_vowel(r.get('pointed') or '') not in ('A', 'O', 'U'): continue   # the checker asks for "a"
            V = LT.verdict(c, want, r)
            if V['v'] != 'right': continue
            good.append((margin(r, want), r))
        good.sort(key=lambda t: -t[0])
        seen, chosen = set(), []
        for m, r in good:
            w = hl(r['w'])
            if w in seen: continue
            seen.add(w); chosen.append(r)
            if len(chosen) >= N: break
        if (c, want) == ('ב', 'v'): chosen = medial_examples(c, want, N)
        exs = []
        for i, r in enumerate(chosen):
            name = f"{SLUG[c]}{('-' + want) if want else ''}-{i + 1}.mp3"
            t0 = max(0.0, r['t0'] - 0.12); dur = r['t1'] - r['t0'] + 0.27
            cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', f'{t0:.3f}', '-i', os.path.join(MP3, r['rec']), '-t', f'{dur:.3f}', '-ac', '1', '-ar', '22050',
                   '-af', f'afade=t=in:d=0.02,afade=t=out:st={max(0, dur - 0.04):.3f}:d=0.04', '-b:a', '40k', os.path.join(OUT_DIR, name)]
            subprocess.run(cmd, check=True)
            exs.append({'w': r['w'], 'pointed': r.get('pointed'), 'per': r['per'], 'ps': r['ps'], 'k': r.get('k', 0) if (c, want) == ('ב', 'v') else 0, 'audio': name, 'dur': round(dur, 2), 'vow': r.get('vow')})
        entry['examples'][want or ''] = exs
        print(f"{c} {want or '':3s} candidates {len(R):4d} right-and-clean {len(good):4d} -> {len(exs)}: {' '.join(e['pointed'] or e['w'] for e in exs)}")
    out['letters'].append(entry)
json.dump(out, open(os.path.join(SPACE, 'static', 'letters.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('wrote static/letters.json and', len(os.listdir(OUT_DIR)), 'mp3s,', sum(os.path.getsize(os.path.join(OUT_DIR, f)) for f in os.listdir(OUT_DIR)) // 1024, 'KB')
