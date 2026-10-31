"""shva_study.py again, through shva.probe itself, with two short-vowel slots: SCHWA (e-like phones) and ALLV (any
vowel — a shva na before a guttural or a yod takes the next vowel's colour). Rows: one per sheva, both readings.
usage: shva_study2.py [perakim | all] [out.json]"""
import sys, os, json, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app, shva as SH
SR = 16000
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
arg = sys.argv[1] if len(sys.argv) > 1 else '1,23,121'
PER = sorted(IDX['perakim'], key=int) if arg == 'all' else arg.split(',')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'shva_rows2.json')
def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(HERE, '..', 'alouf', 'mp3', fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()
rows = []; t_start = time.time()
for n in PER:
    rec = IDX['perakim'].get(str(n))
    if not rec: continue
    for i, p in enumerate(rec['pesukim']):
        if p['t0'] is None or not p.get('nikud'): continue
        x = cut(rec['original'], p['t0'] - .15, p['t1'] + .2)
        if x.shape[0] < SR * .5: continue
        try:
            lp, spf, _ = app.run_model(x)
            a, _ = SH.probe(lp, p['nikud'], app.VOCAB, app.PAD, SH.SCHWA); b, _ = SH.probe(lp, p['nikud'], app.VOCAB, app.PAD, SH.ALLV)
            words = [w for w, _, _ in __import__('nikud').parse_verse(p['nikud'])]
            for wi, slots in a.items():
                for s in slots:
                    t = next((q for q in b.get(wi, []) if q['k'] == s['k']), None)
                    rows.append({'per': int(n), 'ps': i, 'wi': wi, 'word': words[wi], 'k': s['k'], 'c': s['c'], 'kind': s['kind'], 'rule': s['rule'],
                                 'A': {k: s[k] for k in ('used', 'mass', 'gapmax', 'heard')}, 'B': {k: t[k] for k in ('used', 'mass', 'gapmax', 'heard')} if t else None,
                                 'gap_f': s['g1'] - s['g0'] if s['g0'] >= 0 else None, 'last_word': wi == len(words) - 1})
        except Exception as e:
            print('  skipped', n, i, e, flush=True)
    print(f'perek {n}: {len(rows)} shvas so far, {time.time() - t_start:.0f} s', flush=True)
    json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
