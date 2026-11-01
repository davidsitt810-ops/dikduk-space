"""A new reader's Tehillim, the Alouf way (alouf_align.py): both ears over the recording, the pointed text of each perek
force-aligned on them, so for every pasuk and word we get times, and for every letter and vowel which sound he made
(the "register": does he say ע and ח from the throat? which vowel for each mark?).

Two kinds of recording:
  one file per perek   path:perek                 (Shmuelof: hbofPsa_023.mp3:23)
  one file for a book  path:book:<perakim>        (Be'eri: 19_psalms.mp3:book:1-49,113-150)
For a book the perakim are found one after another: each stretch of text (a perek, or ~25 pesukim of a long one) is
aligned LOCALLY inside a window that starts where the last stretch ended: the path may start and end anywhere in the
window (free states before and after, scored as the best symbol of each frame), so announcements, pauses and the
next perek are not forced onto the text.

usage: voice_register.py <out dir> <job> [<job> ...]
writes <out dir>/align/<perek>.json (same shape as tehillim/align) and <out dir>/log.txt"""
import sys, os, json, time, subprocess
import numpy as np, torch
TEH = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad/tehillim'
sys.path.insert(0, TEH)
from nikud import parse_verse, clean_verse
from ctcutil import ctc_align, with_virtual_columns
from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor, Wav2Vec2Processor
from huggingface_hub import hf_hub_download
torch.set_num_threads(int(os.environ.get('THREADS', '2')))
OUT = sys.argv[1]; JOBS = sys.argv[2:]
os.makedirs(os.path.join(OUT, 'align'), exist_ok=True); os.makedirs(os.path.join(OUT, 'feat'), exist_ok=True)
T = json.load(open(os.environ.get('TEXT') or os.path.join(TEH, 'tehillim_nikud.json'), encoding='utf-8'))   # TEXT: another book's {chapter: [verses]} (fetch_texts.py), e.g. Esther
PH_ID = 'facebook/wav2vec2-xlsr-53-espeak-cv-ft'; AR_ID = 'jonatasgrosman/wav2vec2-large-xlsr-53-arabic'
FE = Wav2Vec2FeatureExtractor.from_pretrained(PH_ID); PH = Wav2Vec2ForCTC.from_pretrained(PH_ID).eval()
PH_V = json.load(open(hf_hub_download(PH_ID, 'vocab.json'), encoding='utf-8')); PH_PAD = PH_V['<pad>']
AR_PROC = Wav2Vec2Processor.from_pretrained(AR_ID); AR = Wav2Vec2ForCTC.from_pretrained(AR_ID).eval()
AR_V = AR_PROC.tokenizer.get_vocab(); AR_PAD = AR_PROC.tokenizer.pad_token_id
AR_ALT = {'א': ['ع', 'ا', 'أ', 'ء'], 'ב': ['ب'], 'ג': ['ج', 'غ'], 'ד': ['د', 'ذ'], 'ה': ['ه'], 'ו': ['و'], 'ז': ['ز'], 'ח': ['ح', 'خ', 'ه'], 'ט': ['ط', 'ت'],
          'י': ['ي'], 'כ': ['ك', 'خ'], 'ל': ['ل'], 'מ': ['م'], 'נ': ['ن'], 'ס': ['س'], 'ע': ['ع', 'ا', 'أ', 'ء'], 'פ': ['ف', 'ب'], 'צ': ['ص', 'س'],
          'ק': ['ق', 'ك'], 'ר': ['ر'], 'ש': ['ش', 'س'], 'ת': ['ت', 'ث']}
AR_ALT = {h: [c for c in cs if c in AR_V] for h, cs in AR_ALT.items()}
LOG = open(os.path.join(OUT, 'log.txt'), 'a', encoding='utf-8')
def say(m): print(m, flush=True); LOG.write(m + '\n'); LOG.flush()
say('models ready')

def decode(path):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True, timeout=3600)
    return np.frombuffer(out.stdout, dtype=np.float32).copy()

def run_long(x, which, win=20.0, pad=1.0, note=None):
    """the model over the whole recording in windows of `win` s with `pad` s of context each side (dropped after)"""
    SR = 16000; n = x.shape[0]; lps = []; t0 = 0.0; tick = time.time()
    while True:
        a = max(0.0, t0 - pad); b = min(n / SR, t0 + win + pad)
        seg = x[int(a * SR):int(b * SR)]
        if seg.shape[0] < SR * 0.5: break
        if which == 'ph':
            inp = FE(seg, sampling_rate=SR, return_tensors='pt')
            with torch.inference_mode(): o = PH(inp.input_values)
        else:
            inp = AR_PROC(seg, sampling_rate=SR, return_tensors='pt')
            with torch.inference_mode(): o = AR(inp.input_values)
        lp = torch.log_softmax(o.logits[0], -1).numpy()
        spf = (b - a) / lp.shape[0]
        f0 = int(round((t0 - a) / spf)); f1 = int(round((min(t0 + win, n / SR) - a) / spf))
        lps.append(lp[f0:f1].astype(np.float16))
        if note and time.time() - tick > 300: say(f'  {note} {which}: {t0 / 60:.0f} of {n / SR / 60:.0f} min'); tick = time.time()
        if t0 + win >= n / SR: break
        t0 += win
    lp = np.concatenate(lps)
    return lp, (n / SR) / lp.shape[0]

def ctc_local(lp, toks, blank, vocab_n, pen=0.05):
    """Viterbi over [free-before] + blank-interleaved tokens + [free-after]; the free states score each frame's best
    real symbol minus `pen`. -> (per token {'f0','f1','score'} or f0=-1, first frame, end frame) in window frames"""
    Tn = lp.shape[0]; S = 2 * len(toks) + 1
    ext = np.array([blank if s % 2 == 0 else toks[(s - 1) // 2] for s in range(S)])
    skip_ok = np.array([s > 1 and ext[s] != blank and ext[s] != ext[s - 2] for s in range(S)])
    free = lp[:, :vocab_n].max(1) - pen
    NEG = -1e30
    pre = free[0]; cur = np.full(S, NEG); cur[0] = lp[0, ext[0]]
    if S > 1: cur[1] = lp[0, ext[1]]
    post = NEG
    bp = np.zeros((Tn, S), dtype=np.int8)          # 0 stay, 1 step, 2 skip, 3 from free-before
    bp_post = np.zeros(Tn, dtype=np.int8)          # 0 stay in post, 1 from last blank, 2 from last token
    for t in range(1, Tn):
        prev = cur
        step = np.concatenate(([NEG], prev[:-1])); skip = np.where(skip_ok, np.concatenate(([NEG, NEG], prev[:-2])), NEG)
        best = prev.copy(); b = np.zeros(S, dtype=np.int8)
        m = step > best; best[m] = step[m]; b[m] = 1
        m = skip > best; best[m] = skip[m]; b[m] = 2
        for s0 in (0, 1):                           # entering the text from free-before
            if s0 < S and pre > best[s0]: best[s0] = pre; b[s0] = 3
        # free-after: stay, or arrive from the last blank / last token (their scores at t-1)
        cands = [post, prev[S - 1], prev[S - 2] if S > 1 else NEG]
        k = int(np.argmax(cands)); post = cands[k] + free[t]; bp_post[t] = k
        cur = best + lp[t, ext]; bp[t] = b
        pre = pre + free[t]
    ends = [post, cur[S - 1], cur[S - 2] if S > 1 else NEG]
    k = int(np.argmax(ends))
    path = np.full(Tn, -1, dtype=np.int64)          # -1 free-before, -2 free-after, else state
    t = Tn - 1
    if k == 0:
        while t > 0 and bp_post[t] == 0: path[t] = -2; t -= 1
        if t == 0: return [{'f0': -1, 'f1': -1, 'score': 0.0} for _ in toks], -1, -1
        path[t] = -2; s = S - 1 if bp_post[t] == 1 else S - 2; t -= 1
    else:
        s = S - 1 if k == 1 else S - 2
    while t >= 0:
        path[t] = s
        if t == 0: break
        d = int(bp[t, s])
        if d == 3:
            t -= 1
            while t >= 0: path[t] = -1; t -= 1
            break
        s -= d; t -= 1
    out = [{'f0': -1, 'f1': -1, 'sum': 0.0, 'n': 0} for _ in toks]
    for t in range(Tn):
        st = int(path[t])
        if st < 0 or st % 2 == 0: continue
        o = out[(st - 1) // 2]
        if o['f0'] < 0: o['f0'] = t
        o['f1'] = t + 1; o['sum'] += float(np.exp(lp[t, ext[st]])); o['n'] += 1
    inside = np.where(path >= 0)[0]
    first = int(inside[0]) if len(inside) else -1; last = int(inside[-1]) + 1 if len(inside) else -1
    return [{'f0': o['f0'], 'f1': o['f1'], 'score': (o['sum'] / o['n']) if o['n'] else 0.0} for o in out], first, last

def units_of(verses, v_base=0):
    units = []
    for vi, v in enumerate(verses):
        for wi, (w, letters, us) in enumerate(parse_verse(v)):
            for u in us: units.append({**u, 'v': v_base + vi, 'w': wi, 'word': letters})
    return units

def ph_tokens(units):
    sets, alt_list, toks = {}, [], []
    for u in units:
        key = ','.join(u['alts'])
        if key not in sets: sets[key] = len(alt_list); alt_list.append(u['alts'])
        toks.append(sets[key])
    return alt_list, toks

def place_units(units, ph_lp, f_off, al):
    for u, a in zip(units, al):
        u['f0'] = a['f0'] + f_off if a['f0'] >= 0 else -1; u['f1'] = a['f1'] + f_off if a['f0'] >= 0 else -1; u['p'] = round(a['score'], 3)
        if a['f0'] >= 0:
            mass = {m: float(np.exp(ph_lp[u['f0']:u['f1'], PH_V[m]].astype(np.float32)).sum()) for m in u['alts'] if m in PH_V}
            u['heard'] = max(mass, key=mass.get) if mass else None; u['mass'] = {m: round(v, 3) for m, v in mass.items()}

def ar_letters_of(verses, ar_lp, f0, f1, v_base=0):
    """the Arabic-letter ear's verdict on every letter, aligned on [f0, f1) of its frames"""
    toks, meta, alt_list, sets = [], [], [], {}
    for vi, v in enumerate(verses):
        for wi, (w, letters, us) in enumerate(parse_verse(v)):
            for k, c in enumerate(letters):
                if c == 'ה' and k == len(letters) - 1: continue
                alts = AR_ALT.get(c)
                if not alts: continue
                key = ','.join(alts)
                if key not in sets: sets[key] = len(alt_list); alt_list.append(alts)
                toks.append(sets[key]); meta.append((v_base + vi, wi, k, c))
    seg = ar_lp[f0:f1].astype(np.float32)
    lp2, ids = with_virtual_columns(seg, alt_list, AR_V)
    S = 2 * len(toks) + 1; Tn = lp2.shape[0]
    band = None if Tn * S < 150_000_000 else max(1500, int(S * 0.12))
    al = ctc_align(lp2, [ids[t] for t in toks], AR_PAD, band=band)
    out = []
    for (vi, wi, k, c), a in zip(meta, al):
        r = {'v': vi, 'w': wi, 'k': k, 'c': c, 'f0': a['f0'] + f0 if a['f0'] >= 0 else -1, 'f1': a['f1'] + f0 if a['f0'] >= 0 else -1, 'p': round(a['score'], 3)}
        if a['f0'] >= 0:
            mass = {m: float(np.exp(seg[a['f0']:a['f1'], AR_V[m]]).sum()) for m in AR_ALT[c]}
            r['heard'] = max(mass, key=mass.get); r['mass'] = {m: round(v, 3) for m, v in mass.items()}
        out.append(r)
    return out

def spans(units, spf, verses):
    vs = []
    for vi, v in enumerate(verses):
        us = [u for u in units if u['v'] == vi and u.get('f0', -1) >= 0]
        nw = max([u['w'] for u in units if u['v'] == vi], default=-1) + 1; words = []
        for wi in range(nw):
            uw = [u for u in us if u['w'] == wi]
            if uw: words.append({'w': uw[0]['word'], 't0': round(min(u['f0'] for u in uw) * spf, 3), 't1': round(max(u['f1'] for u in uw) * spf, 3), 'p': round(float(np.mean([u['p'] for u in uw])), 3)})
            else: words.append({'w': next((u['word'] for u in units if u['v'] == vi and u['w'] == wi), '?'), 't0': None, 't1': None, 'p': 0})
        vs.append({'n': vi + 1, 'text': clean_verse(v), 'nikud': v, 't0': words[0]['t0'] if words and words[0]['t0'] is not None else None,
                   't1': max([w['t1'] for w in words if w['t1'] is not None], default=None), 'p': round(float(np.mean([u['p'] for u in us])), 3) if us else 0, 'words': words})
    return vs

def finish(n, src, dur, spf, spf2, units, ar_letters, verses, extra):
    for u in units: u.pop('alts', None)
    placed = [u for u in units if u.get('f0', -1) >= 0]
    q = {'units': len(units), 'placed': len(placed), 'mean_p': round(float(np.mean([u['p'] for u in placed])), 3) if placed else 0,
         'good': round(float(np.mean([u['p'] > .3 for u in placed])), 3) if placed else 0, 'ar_mean_p': round(float(np.mean([a['p'] for a in ar_letters if a['f0'] >= 0] or [0])), 3)}
    vs = spans(units, spf, verses)
    json.dump({'perek': n, 'file': os.path.basename(src), 'dur': round(dur, 2), 'spf': spf, 'spf_ar': spf2, 'quality': q, **extra, 'pesukim': vs, 'units': units, 'ar_letters': ar_letters},
              open(os.path.join(OUT, 'align', f'{n}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return q

def perakim_of(spec):
    out = []
    for part in spec.split(','):
        a, _, b = part.partition('-'); out += list(range(int(a), int(b or a) + 1))
    return out

t_start = time.time()
AR_SET = os.environ.get('AR', 'all'); AR_SET = None if AR_SET == 'all' else set(perakim_of(AR_SET)) if AR_SET else set()   # perakim for the Arabic ear
for job in JOBS:
    path, _, rest = job.partition(':')
    if rest.startswith('book:'):
        # ---------- one file, many perakim, found in order ----------
        P = perakim_of(rest[5:]); base = os.path.basename(path)
        fz = os.path.join(OUT, 'feat', base + '.npz'); fp = os.path.join(OUT, 'feat', base + '.ph.npz'); ar_lp = None; spf2 = None
        if os.path.exists(fz):                                # (the first test: both ears over the whole file)
            z = np.load(fz); ph_lp, ar_lp, spf, spf2, dur = z['ph_lp'], z['ar_lp'], float(z['spf']), float(z['spf2']), float(z['dur'])
        elif os.path.exists(fp):
            z = np.load(fp); ph_lp, spf, dur = z['ph_lp'], float(z['spf']), float(z['dur'])
        else:                                                 # the phone ear over the whole book (the Arabic ear later, per perek),
            dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                                       capture_output=True, text=True).stdout.strip())
            say(f'{base}: {dur / 60:.1f} min of audio'); BLOCK = float(os.environ.get('BLOCK', 1800)); blocks = []; k = 0
            while k * BLOCK < dur:                            # in 30-minute blocks kept on disk, so a stopped run picks up where it was
                fb = os.path.join(OUT, 'feat', f'{base}.ph.{k:02d}.npy')
                if os.path.exists(fb): blocks.append(np.load(fb)); k += 1; continue
                b0 = k * BLOCK; b1 = min(dur, b0 + BLOCK); a0 = max(0.0, b0 - 1.0); a1 = min(dur, b1 + 1.0)
                xr = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a0:.3f}', '-i', path, '-t', f'{a1 - a0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                                    capture_output=True, timeout=1800).stdout
                lpb, spf_b = run_long(np.frombuffer(xr, dtype=np.float32).copy(), 'ph', note=f'{base} block {k}')
                f0 = int(round((b0 - a0) / spf_b)); f1 = min(lpb.shape[0], f0 + int(round((b1 - b0) / spf_b)))
                np.save(fb, lpb[f0:f1]); blocks.append(lpb[f0:f1]); k += 1
                say(f'  phone ear block {k} of {int(np.ceil(dur / BLOCK))} [{int(time.time() - t_start)} s]')
            ph_lp = np.concatenate(blocks); spf = dur / ph_lp.shape[0]
            np.savez(fp, ph_lp=ph_lp, spf=spf, dur=dur)
        nV = len(PH_V); rate = None; pos = 0                 # pos: phone-ear frame where the next text should start
        for n in P:
            if os.path.exists(os.path.join(OUT, 'align', f'{n}.json')):
                A = json.load(open(os.path.join(OUT, 'align', f'{n}.json'), encoding='utf-8')); pos = A['f_end']; rate = A.get('rate', rate); continue
            verses = T[str(n)]; units = []; chunks = []; pos_in = pos
            step = 25 if len(verses) > 40 else len(verses)
            for c0 in range(0, len(verses), step):
                cu = units_of(verses[c0:c0 + step], v_base=c0); chunks.append(cu); units += cu
            first = None
            for cu in chunks:
                alt_list, toks = ph_tokens(cu)
                est = len(cu) * (rate if rate else 0.2) / spf                            # frames the stretch should take
                W0 = pos; W1 = min(ph_lp.shape[0], int(pos + est * (1.6 if rate else 3.0) + 45 / spf))
                seg = ph_lp[W0:W1].astype(np.float32)
                lp2, ids = with_virtual_columns(seg, alt_list, PH_V)
                tok_ids = [ids[t] for t in toks]; keep = [i for i, t in enumerate(tok_ids) if t is not None]
                al, f_a, f_b = ctc_local(lp2, [tok_ids[i] for i in keep], PH_PAD, nV)
                full = [{'f0': -1, 'f1': -1, 'score': 0.0} for _ in cu]
                for i, a in zip(keep, al): full[i] = a
                place_units(cu, ph_lp, W0, full)
                if f_a < 0: say(f'  perek {n}: a stretch was not found in {W0 * spf:.0f}-{W1 * spf:.0f} s'); continue
                if first is None: first = W0 + f_a
                pos = W0 + f_b
            placed = [u for u in units if u['f0'] >= 0]
            mp = float(np.mean([u['p'] for u in placed])) if placed else 0.0
            if first is None or not placed or mp < 0.35:       # not in the recording (or not here): don't move on
                say(f'perek {n}: NOT FOUND near {pos_in * spf / 60:.2f} min (mean p {mp:.2f})'); pos = pos_in; continue
            f_beg = min(u['f0'] for u in placed); f_end = max(u['f1'] for u in placed)
            took = (f_end - f_beg) * spf; r_here = took / max(1, len(units))
            rate = r_here if rate is None else 0.7 * rate + 0.3 * r_here
            if ar_lp is not None:
                f2a = int(f_beg * spf / spf2); f2b = min(ar_lp.shape[0], int(f_end * spf / spf2) + 10)
                arl = ar_letters_of(verses, ar_lp, f2a, f2b)
            elif AR_SET is None or n in AR_SET:              # the Arabic ear on this perek's stretch only
                a_pad = min(0.3, f_beg * spf); a_t0 = f_beg * spf - a_pad; a_t1 = f_end * spf + 0.3
                xr = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a_t0:.3f}', '-i', path, '-t', f'{a_t1 - a_t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                                    capture_output=True, timeout=600).stdout
                ar_r, spf2 = run_long(np.frombuffer(xr, dtype=np.float32).copy(), 'ar')
                arl = ar_letters_of(verses, ar_r, 0, ar_r.shape[0]); f2a = int(round(a_pad / spf2))   # times from the perek's start
            else:
                arl = []; f2a = 0; spf2 = spf2 or spf
            # times relative to the perek's own start (as for a one-perek file), plus where it sits in the book
            off = f_beg
            for u in units:
                if u['f0'] >= 0: u['f0'] -= off; u['f1'] -= off
            for a in arl:
                if a['f0'] >= 0: a['f0'] -= f2a; a['f1'] -= f2a
            q = finish(n, path, took, spf, spf2, units, arl, verses, {'book_t0': round(f_beg * spf, 3), 'book_t1': round(f_end * spf, 3), 'f_end': int(f_end), 'rate': rate})
            pos = f_end
            say(f'perek {n}: {f_beg * spf / 60:.2f}-{f_end * spf / 60:.2f} min ({took:.0f} s), units {q["units"]} placed {q["placed"]} mean p {q["mean_p"]} good {q["good"]} ar {q["ar_mean_p"]}  [{int(time.time() - t_start)} s]')
    else:
        # ---------- one perek per file ----------
        n = int(rest)
        if os.path.exists(os.path.join(OUT, 'align', f'{n}.json')): continue
        x = decode(path); dur = x.shape[0] / 16000; verses = T[str(n)]; do_ar = AR_SET is None or n in AR_SET
        ph_lp, spf = run_long(x, 'ph'); ar_lp, spf2 = run_long(x, 'ar') if do_ar else (None, spf)
        units = units_of(verses); alt_list, toks = ph_tokens(units)
        lp2, ids = with_virtual_columns(ph_lp.astype(np.float32), alt_list, PH_V)
        tok_ids = [ids[t] for t in toks]; keep = [i for i, t in enumerate(tok_ids) if t is not None]
        al, f_a, f_b = ctc_local(lp2, [tok_ids[i] for i in keep], PH_PAD, len(PH_V))
        full = [{'f0': -1, 'f1': -1, 'score': 0.0} for _ in units]
        for i, a in zip(keep, al): full[i] = a
        place_units(units, ph_lp, 0, full)
        arl = ar_letters_of(verses, ar_lp, 0, ar_lp.shape[0]) if do_ar else []
        q = finish(n, path, dur, spf, spf2, units, arl, verses, {})
        say(f'perek {n} ({os.path.basename(path)}): {dur:.0f} s, units {q["units"]} placed {q["placed"]} mean p {q["mean_p"]} good {q["good"]} ar {q["ar_mean_p"]}  [{int(time.time() - t_start)} s]')
say('done')
