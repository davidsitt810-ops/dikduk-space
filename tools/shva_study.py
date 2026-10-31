"""Can the ears hear a shva na? Rabbi Alouf's Tehillim, every sheva marked na/nah by the Sephardic rules (shva.py):
the pasuk's sounds (nikud.py units) are force-aligned on the phone ear with an OPTIONAL short-vowel slot after every
consonant that carries a sheva; for each slot: was it used, how much short-vowel mass it holds, and the strongest
short-vowel frame between that consonant and the next sound. If the ears can hear it, the na rules should show a
vowel far more often than the nah rules.
usage: shva_study.py [perakim (comma list) | all] [out.json]"""
import sys, os, json, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app
from nikud import parse_verse
from shva import shva_marks
from vowels import ctc_align_opt
SR = 16000
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
arg = sys.argv[1] if len(sys.argv) > 1 else '1,23,121'
PER = sorted(IDX['perakim'], key=int) if arg == 'all' else [p for p in arg.split(',')]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'shva_rows.json')
SCHWA = [p for p in ['ə', 'ɛ', 'e', 'ɪ', 'ɨ', 'ɐ', 'ʌ', 'e̞', 'ɛː', 'eː'] if p in app.VOCAB]
def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(HERE, '..', 'alouf', 'mp3', fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()

def template(pointed):
    """-> toks (column keys), meta per token, optional slot positions; keys are tuples of phones (a virtual column)"""
    toks, meta, opt = [], [], set()
    for wi, (w, letters, units) in enumerate(parse_verse(pointed)):
        sh = {m['k']: m for m in shva_marks(w)}
        for u in units:
            alts = tuple(p for p in (u['alts'] or []) if p in app.VOCAB)
            if not alts: continue
            toks.append(alts); meta.append({'w': wi, 'k': u['k'], 'kind': u['kind'], 'c': u['c']})
            if u['kind'] == 'cons' and u['k'] in sh and not sh[u['k']].get('_done'):
                sh[u['k']]['_done'] = True
                opt.add(len(toks)); toks.append(tuple(SCHWA)); meta.append({'w': wi, 'k': u['k'], 'kind': 'slot', 'c': u['c'], 'm': sh[u['k']], 'word': w})
    return toks, meta, opt

def run_pasuk(x, pointed):
    lp, spf, _ = app.run_model(x)
    toks, meta, opt = template(pointed)
    if not toks: return []
    keys = sorted(set(toks) | {tuple(SCHWA)}); col = {k: lp.shape[1] + i for i, k in enumerate(keys)}
    lp2 = np.concatenate([lp, np.stack([np.logaddexp.reduce(lp[:, [app.VOCAB[p] for p in k]], axis=1) for k in keys], 1)], 1)
    al = ctc_align_opt(lp2, [col[k] for k in toks], app.PAD, optional=opt, skip_cost=0.0)
    sch = np.exp(lp2[:, col[tuple(SCHWA)]])
    rows = []
    for j, (m, a) in enumerate(zip(meta, al)):
        if m['kind'] != 'slot': continue
        prev = al[j - 1]; nxt = next((al[q] for q in range(j + 1, len(al)) if al[q]['f0'] >= 0), None)
        g0 = prev['f1'] if prev['f0'] >= 0 else None; g1 = nxt['f0'] if nxt else lp.shape[0]
        gap = sch[g0:g1] if g0 is not None and g1 > g0 else np.zeros(0)
        own = sch[a['f0']:a['f1']] if a['f0'] >= 0 else np.zeros(0)
        rows.append({'word': m['word'], 'k': m['k'], 'c': m['c'], 'kind': m['m']['kind'], 'rule': m['m']['rule'],
                     'used': a['f0'] >= 0, 'mass': round(float(own.sum()), 3), 'slot_f': int(a['f1'] - a['f0']) if a['f0'] >= 0 else 0,
                     'gapmax': round(float(gap.max()), 3) if gap.size else 0.0, 'gap_f': int(gap.size), 'cons_p': round(prev['score'], 3) if prev['f0'] >= 0 else None,
                     'last_word': m['w'] == max(mm['w'] for mm in meta)})
    return rows

if __name__ == '__main__':
    rows = []; t_start = time.time()
    for n in PER:
        rec = IDX['perakim'].get(str(n))
        if not rec: continue
        for i, p in enumerate(rec['pesukim']):
            if p['t0'] is None or not p.get('nikud'): continue
            x = cut(rec['original'], p['t0'] - .15, p['t1'] + .2)
            if x.shape[0] < SR * .5: continue
            try:
                for r in run_pasuk(x, p['nikud']): r.update(per=int(n), ps=i); rows.append(r)
            except Exception as e:
                print('  skipped', n, i, e, flush=True)
        print(f'perek {n}: {len(rows)} shvas so far, {time.time() - t_start:.0f} s', flush=True)
        json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    # the table: per rule, how often a vowel is heard
    import collections
    by = collections.defaultdict(list)
    for r in rows: by[(r['kind'], r['rule'])].append(r)
    print(f"\n{'rule':16s} {'n':>5s} {'slot used':>10s} {'mass≥.5':>8s} {'gapmax≥.3':>10s}  median mass")
    for (kind, rule), rs in sorted(by.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        u = np.mean([r['used'] for r in rs]); m5 = np.mean([r['mass'] >= .5 for r in rs]); g3 = np.mean([r['gapmax'] >= .3 for r in rs])
        print(f"{kind + ' ' + rule:16s} {len(rs):5d} {u:10.0%} {m5:8.0%} {g3:10.0%}  {np.median([r['mass'] for r in rs]):.2f}")
