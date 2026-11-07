"""The checker on a reader it has never heard. Each of his pesukim is the student's take; the hazzan is Rabbi Alouf's
recording of the same pasuk and the perek's other pesukim are the rival lines, as the site checks Tehillim. Through
the live server (/check) and the page's own rule (rule.summarize). Only his intact reading, so every word is right:
every ✕ is a false alarm, every "not sure" a word the checker could not confirm, every throat "plain" / vowel note /
shva note a claim to look at (a fault of the checker, or a real difference of his reading from the nikud).
usage: exam_voice.py <align dir> <audio> <name> [N=150] [seed=7]
  <audio>: the book file (perakim carry book_t0), or a per-perek file pattern with {n} (e.g. .../hbofPsa_{n:03d}.mp3)
writes exam_<name>.json next to this script and prints the summary"""
import sys, os, json, random, subprocess, time, collections
import requests
REPO = '/home/claude/dikduk-space'; sys.path.insert(0, REPO)
import rule
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(HERE)
AL, SRC, NAME = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 150; SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 7
BASE = os.environ.get('DK_URL', 'http://127.0.0.1:7861')
IDX = json.load(open(os.path.join(S, 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))['perakim']
def perakim_of(spec):
    out = []
    for part in spec.split(','):
        a, _, b = part.partition('-'); out += list(range(int(a), int(b or a) + 1))
    return set(out)
ONLY = perakim_of(os.environ['PERAKIM']) if os.environ.get('PERAKIM') else None   # e.g. the held-out perakim
jobs = []
for f in sorted(os.listdir(AL)):
    if not f.endswith('.json'): continue
    A = json.load(open(os.path.join(AL, f), encoding='utf-8')); n = A['perek']
    if ONLY is not None and n not in ONLY: continue
    R = IDX.get(str(n))
    if not R or len(R['pesukim']) != len(A['pesukim']): continue
    for i, (p, q) in enumerate(zip(A['pesukim'], R['pesukim'])):
        if p['t0'] is None or q['t0'] is None or q['t1'] is None or len(p['words']) < 3 or any(w['t0'] is None for w in p['words']): continue
        if p['p'] < .45 or p['t1'] - p['t0'] > 30: continue      # the alignment itself is doubtful / too long for one take
        jobs.append((n, i))
random.seed(SEED); random.shuffle(jobs); jobs = jobs[:N]
if os.environ.get('ONLY_PS'):   # re-check just these pesukim (perek:pasuk from 1), e.g. after a fix
    want_ps = {tuple(int(x) for x in s.split(':')) for s in os.environ['ONLY_PS'].split(',')}
    jobs = [(n, i) for n, i in jobs if (n, i + 1) in want_ps]
print(f'{NAME}: {len(jobs)} pesukim', flush=True)
# PLANT=OU: a planted mistake (tools/mistake_lab.py) — the page's o-vowels written u (holam, kamatz katan, hataf kamatz ->
# kubutz; holam male -> shuruk), the Name kept, so the correct reader now "says o where the page says u". Run it with
# NO_REF=1: the reader says those vowels exactly as the hazzan does, and the hazzan comparison (and the v4.9 rule that
# drops a nikud note the hazzan shares) would hide every planted mistake. Rows get 'planted' (word indices) and 'nw'.
PLANT = os.environ.get('PLANT'); NO_REF = bool(os.environ.get('NO_REF'))
RAW = bool(os.environ.get('RAW'))   # RAW=1: each row also keeps the vowel ear's slots (take and hazzan) and the server's notes, to try other note rules offline
# PLANT=SKIP: a skipped word — one word of two letters or more, chosen at random (seeded by perek and pasuk), cut out of
# the take's audio (its aligned span, a 10 ms crossfade at the join); the page and the hazzan unchanged, so run it
# WITHOUT NO_REF. Rows get 'planted' [the word] and 'skip_t'; with RAW=1 also each word's drop / swap evidence.
SKIP = PLANT == 'SKIP'
if PLANT and not SKIP:
    assert PLANT in ('OU', 'IE', 'EI', 'EA', 'UO'), 'PLANT=OU, IE, EI, EA, UO or SKIP'
    import nikud as NK
    O_MARKS = {NK.HOLAM, NK.HOLAM_VAV, NK.QAMATS_QATAN, NK.HAT_QAM}
    def plant_word(w):
        if NK.NAME.search(w): return w
        groups = []
        for ch in w:
            if 'א' <= ch <= 'ת' or not groups: groups.append([ch, []])
            else: groups[-1][1].append(ch)
        out = []
        for c, ms in groups:
            if any(m in O_MARKS for m in ms):
                male = c == 'ו' and NK.DAGESH not in ms and not any(m in NK.VOWEL_MARKS and m not in O_MARKS for m in ms)
                ms = [(NK.DAGESH if male else NK.QUBUTS) if m in O_MARKS else m for m in ms]
            out.append(c + ''.join(ms))
        return ''.join(out)
    if PLANT == 'IE':   # the page's hiriq written tsere, the Name kept: the correct reader now "says i where the page says e"
        def plant_word(w): return w if NK.NAME.search(w) else w.replace(NK.HIRIQ, NK.TSERE)
    # the other way round, for the next kinds of false note (LAB_NOTES §39): EI = the page's e (tsere, segol, hataf segol)
    # written hiriq, so the correct reader "says e where the page says i"; EA = written patah (hataf segol -> hataf
    # patah; not an e before a bare yod, which would turn it into the diphthong ay); UO = the page's u written o (kubutz
    # -> holam, shuruk -> holam male). The Name kept.
    TARGET = {'EI': {NK.TSERE: NK.HIRIQ, NK.SEGOL: NK.HIRIQ, NK.HAT_SEG: NK.HIRIQ},
              'EA': {NK.TSERE: NK.PATAH, NK.SEGOL: NK.PATAH, NK.HAT_SEG: NK.HAT_PAT}, 'UO': {NK.QUBUTS: NK.HOLAM}}
    if PLANT in TARGET:
        def plant_word(w):
            if NK.NAME.search(w): return w
            groups = []
            for ch in w:
                if 'א' <= ch <= 'ת' or not groups: groups.append([ch, []])
                else: groups[-1][1].append(ch)
            out = []
            for j, (c, ms) in enumerate(groups):
                nxt = groups[j + 1] if j + 1 < len(groups) else None
                bare_yod = nxt is not None and nxt[0] == 'י' and not any(m in NK.VOWEL_MARKS or m == NK.DAGESH for m in nxt[1])
                if PLANT == 'UO' and c == 'ו' and NK.DAGESH in ms and not any(m in NK.VOWEL_MARKS for m in ms):
                    ms = [NK.HOLAM if m == NK.DAGESH else m for m in ms]   # shuruk -> holam male
                elif not (PLANT == 'EA' and bare_yod):
                    ms = [TARGET[PLANT].get(m, m) for m in ms]
                out.append(c + ''.join(ms))
            return ''.join(out)
    def plant(nik, one=None):
        words = nik.split(' '); news = [plant_word(w) for w in words]
        if one is not None:   # PLANT_ONE=1: one planted word per pasuk, chosen at random (a student rarely misreads more,
            # and a mistake made everywhere would also look like the reader's own way of speaking to a rule that weighs the take)
            cand = [j for j, (a, b) in enumerate(zip(words, news)) if a != b]
            pick = one.choice(cand) if cand else None
            news = [b if j == pick else a for j, (a, b) in enumerate(zip(words, news))]
        new = ' '.join(news)
        a, b = NK.parse_verse(nik), NK.parse_verse(new)
        assert len(a) == len(b)
        idx = [j for j, ((_, _, ua), (_, _, ub)) in enumerate(zip(a, b)) if [u['c'] for u in ua] != [u['c'] for u in ub]]
        return new, idx, len(a)
CACHE = {}
def align(n):
    if n not in CACHE: CACHE[n] = json.load(open(os.path.join(AL, f'{n}.json'), encoding='utf-8'))
    return CACHE[n]
def cut(n, a, b):
    A = align(n)
    if '{n' in SRC: path, off = SRC.format(n=n), 0.0
    else: path, off = SRC, A['book_t0']
    return subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, off + a):.3f}', '-i', path, '-t', f'{b - a:.3f}', '-ac', '1', '-ar', '16000', '-f', 'wav', '-'],
                          capture_output=True, timeout=120).stdout
def cut_skip(n, a, b, wa, wb):
    """the take [a, b] with the span [wa, wb] cut out (a 10 ms crossfade at the join), as a 16 kHz mono wav"""
    import numpy as np, struct
    A = align(n)
    if '{n' in SRC: path, off = SRC.format(n=n), 0.0
    else: path, off = SRC, A['book_t0']
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, off + a):.3f}', '-i', path, '-t', f'{b - a:.3f}', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True, timeout=120).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    i0 = max(0, int(round((wa - a) * 16000))); i1 = min(len(x), max(i0, int(round((wb - a) * 16000)))); f = 160
    head, tail = x[:i0], x[i1:]
    if len(head) >= f and len(tail) >= f:
        r = np.linspace(0, 1, f, dtype=np.float32); y = np.concatenate([head[:-f], head[-f:] * (1 - r) + tail[:f] * r, tail[f:]])
    else: y = np.concatenate([head, tail])
    pcm = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
    return b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, 16000, 32000, 2, 16) + b'data' + struct.pack('<I', len(pcm)) + pcm
# rows are kept as they come (exam_<name>.jsonl), so a stopped run picks up where it was
JL = os.path.join(HERE, f'exam_{NAME}.jsonl'); rows = []
if os.path.exists(JL):
    rows = [json.loads(l) for l in open(JL, encoding='utf-8') if l.strip()]
have = {(r['per'], r['ps']) for r in rows}; jl = open(JL, 'a', encoding='utf-8'); t_start = time.time()
def keep(r):
    rows.append(r); jl.write(json.dumps(r, ensure_ascii=False) + '\n'); jl.flush()
for done, (n, i) in enumerate(jobs, 1):
    if (n, i) in have: continue
    A = align(n); R = IDX[str(n)]; p = A['pesukim'][i]; q = R['pesukim'][i]; skip_t = None
    if SKIP:
        cand = [j for j, w in enumerate(p['words']) if len(w['w']) >= 2]
        j = random.Random(n * 1000 + i).choice(cand); skip_t = [p['words'][j]['t0'], p['words'][j]['t1']]
        wav = cut_skip(n, p['t0'] - .25, p['t1'] + .25, *skip_t); nik, planted, nw = q['nikud'], [j], len(p['words'])
    else: wav = cut(n, p['t0'] - .25, p['t1'] + .25)
    alts = '|'.join(x['text'] for k, x in enumerate(R['pesukim']) if k != i and x.get('text'))
    if not SKIP: nik, planted, nw = (plant(q['nikud'], random.Random(n * 1000 + i) if os.environ.get('PLANT_ONE') else None) if PLANT else (q['nikud'], None, None))
    prm = {'words': q['text'], 'nikud': nik, 'alts': alts}
    if not NO_REF: prm.update({'ref': R['file'], 't0': q['t0'], 't1': q['t1']})
    try:
        r = requests.post(BASE + '/check', params=prm, data=wav, headers={'Content-Type': 'application/octet-stream'}, timeout=900)
        out = r.json()
        if r.status_code != 200: keep({'per': n, 'ps': i, 'err': out.get('err', r.status_code)}); continue
    except Exception as e:
        keep({'per': n, 'ps': i, 'err': str(e)[:200]}); continue
    sm = rule.summarize(out)
    keep({'per': n, 'ps': i, 'words': out['words'], 'dur': round(p['t1'] - p['t0'] + .5, 2), 'align_p': p['p'], 'marks': sm['marks'], 'why': sm['why'],
                 'line_wrong': sm['line_wrong'], 'cant_hear': sm['cant_hear'], 'no_speech': sm['no_speech'], 'clean': sm['clean'], 'head': rule.head_median(out['take']['words']),
                 'throat': sm['throat'], 'vowels': sm['vowels'], 'shva': sm['shva'], 'rival': sm['rival'], 'gap': sm['gap'],
                 'strict': rule.strict_of(sm['marks'], sm['why'], sm['clean'], sm['cant_hear'])[0],
                 **({'planted': planted, 'nw': nw} if PLANT else {}),
                 **({'skip_t': skip_t, 'skip_ok': len(out['words']) == nw and out['words'][planted[0]] == p['words'][planted[0]]['w']} if SKIP else {}),
                 **({'raw': {'nikud': nik, 'tw': [[(v['k'], v['heard'], v['mass'], v['p']) for v in (w.get('vow') or [])] for w in out['take']['words']],
                             'rw': [[(v['k'], v['heard'], v['mass'], v['p']) for v in (w.get('vow') or [])] for w in ((out.get('ref') or {}).get('words') or [])],
                             'sv': out.get('vowels'), 'svn': out.get('vowels_nikud'),
                             # the word rule's inputs (rule.marks_of), to try other drop / swap bars offline
                             'rule_in': {'tw': [{k: w.get(k) for k in ('n', 'skel', 'kept', 'pw', 'hskel', 'drop', 'swap')} for w in out['take']['words']],
                                         'fit': [(f or {}).get('fit') for f in (out.get('fit') or [])]}}} if RAW else {})})
    if done % 10 == 0: print(f'  {done}/{len(jobs)}  [{int(time.time() - t_start)} s]', flush=True)
jl.close(); want = set(jobs); rows = [r for r in rows if (r['per'], r['ps']) in want]
json.dump(rows, open(os.path.join(HERE, f'exam_{NAME}.json'), 'w', encoding='utf-8'), ensure_ascii=False)

ok = [r for r in rows if 'err' not in r]
W = sum(len(r['marks']) for r in ok); C = collections.Counter(m for r in ok for m in r['marks'])
CL = [r for r in ok if r['clean']]; Wc = sum(len(r['marks']) for r in CL); Cc = collections.Counter(m for r in CL for m in r['marks'])
St = collections.Counter(m for r in CL for m in r['strict'])
pct = lambda a, b: f'{100 * a / b:.1f}%' if b else '-'
print(f'\n== {NAME}: {len(ok)} takes ({len(rows) - len(ok)} errors), clean {len(CL)} ({pct(len(CL), len(ok))}), line called wrong {sum(r["line_wrong"] for r in ok)}, can\'t hear {sum(r["cant_hear"] for r in ok)}')
print(f'  all words {W}: ✕ {C["off"]} ({pct(C["off"], W)}), not sure {C["unsure"]} ({pct(C["unsure"], W)}), ✓ {C["ok"]} ({pct(C["ok"], W)})')
print(f'  on clean takes {Wc}: ✕ {Cc["off"]} ({pct(Cc["off"], Wc)}), not sure {Cc["unsure"]} ({pct(Cc["unsure"], Wc)}); strict ✕ {St["off"]} ({pct(St["off"], Wc)})')
for c in 'עח':
    th = collections.Counter(t['v'] for r in ok for t in r['throat'] if t['c'] == c); n_ = sum(th.values())
    hz = collections.Counter(t['hazzan'] for r in ok for t in r['throat'] if t['c'] == c)
    print(f'  {c} (n={n_}): throat {pct(th["throat"], n_)}, unsure {pct(th["unsure"], n_)}, plain {pct(th["plain"], n_)}   | the hazzan on the same letters: ' + ', '.join(f'{k} {v}' for k, v in hz.most_common()))
nv = sum(len(r['vowels']) for r in ok); ns = sum(len(r['shva']) for r in ok)
print(f'  vowel notes {nv} ({pct(nv, Wc)} of clean words): ' + ', '.join(f'{a}->{b} {k}' for (a, b), k in collections.Counter((v['ref'], v['you']) for r in ok for v in r['vowels']).most_common(6)))
print(f'  shva notes {ns}: ' + ', '.join(f'{k} {v}' for k, v in collections.Counter((s['want'], s['you'], s['rule']) for r in ok for s in r['shva']).most_common(6)))
fa = [(r['per'], r['ps'] + 1, r['words'][k], r['why'][k], round(r['head'] or 0, 2)) for r in ok for k, m in enumerate(r['marks']) if m == 'off']
print(f'  false alarms ({len(fa)}):', *fa[:25], sep='\n    ')
