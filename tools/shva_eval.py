"""The shva check examined on Rabbi Alouf's held-out perakim, the way a student errs:
  intact   his own reading against the rules — every note here is a false alarm (he reads it right)
  drop     a shva na he says, its short vowel CUT out of the audio — does the check now say "say a short e"?
  add      a shva nah he leaves silent, a short vowel (his own, from a shva na of the same pasuk) PUT IN — does the
           check now say "no vowel"?
Both tampered takes are checked twice: by the rules alone, and against the hazzan (his intact reading, as on the
Space). Collateral = notes that appear elsewhere in the tampered pasuk.
usage: shva_eval.py [perakim] [max pesukim]"""
import sys, os, json, time, random, subprocess, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app, shva as SH
SR = 16000
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
PER = (sys.argv[1].split(',') if len(sys.argv) > 1 and sys.argv[1] != 'held' else ['7', '12', '18', '21', '23', '32', '35', '40', '46', '94', '118', '123', '126', '140'])
MAXP = int(sys.argv[2]) if len(sys.argv) > 2 else 400
random.seed(7)
def cut(fname, t0, t1):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', os.path.join(HERE, '..', 'alouf', 'mp3', fname), '-t', f'{t1 - t0:.3f}', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()
def probe(x, nikud):
    lp, spf, _ = app.run_model(x); sv, nw = SH.probe(lp, nikud, app.VOCAB, app.PAD)
    return {str(i): v for i, v in sv.items()}, spf
XF = int(0.004 * SR)
def splice(a, b):
    """a then b with a 4 ms crossfade"""
    if len(a) < XF or len(b) < XF: return np.concatenate([a, b])
    w = np.linspace(0, 1, XF, dtype=np.float32)
    return np.concatenate([a[:-XF], a[-XF:] * (1 - w) + b[:XF] * w, b[XF:]])
def slot(sv, w, k): return next((s for s in sv.get(w, []) if s['k'] == k), None)
def note_at(notes, w, k): return any(n['k'] == k for n in notes.get(w, []))
def others(notes, w, k): return sum(1 for ww, ns in notes.items() for n in ns if not (ww == w and n['k'] == k))
C = collections.Counter(); rows = []; feats = []; t_start = time.time(); done = 0
jobs = [(n, i) for n in PER for i, p in enumerate(IDX['perakim'][n]['pesukim']) if p['t0'] is not None and p.get('nikud')]
random.shuffle(jobs); jobs = jobs[:MAXP]
for n, i in jobs:
    rec = IDX['perakim'][n]; p = rec['pesukim'][i]
    x = cut(rec['original'], p['t0'] - .15, p['t1'] + .2)
    if x.shape[0] < SR * .5: continue
    sv, spf = probe(x, p['nikud'])
    if not sv and not any(True for _ in sv): pass
    rule_notes = SH.notes(sv, None)
    for w, ss in sv.items():
        for s in ss:
            feats.append({'case': 'intact', 'per': n, 'ps': i, 'w': w, 'k': s['k'], 'kind': s['kind'], 'rule': s['rule'], 'f': {k: s[k] for k in ('used', 'mass', 'gapmax', 'used_any', 'mass_any', 'gapmax_any', 'heard')}})
            if s['rule'] in SH.TRUSTED:
                C['intact slots (trusted)'] += 1; C[f"intact heard {s['heard']} ({s['kind']})"] += 1
    C['intact notes (false alarms)'] += sum(len(v) for v in rule_notes.values()); C['pesukim'] += 1
    C['pesukim with a false alarm'] += bool(rule_notes)
    for ww, ns in rule_notes.items():
        for nn in ns: rows.append({'case': 'intact', 'per': n, 'ps': i, **nn, 'word': next((s for s in sv[ww] if s['k'] == nn['k']), {}).get('mass')})
    # drop: cut out the vowel of a trusted shva na he said
    na = [(w, s) for w, ss in sv.items() for s in ss if s['kind'] == 'na' and s['rule'] in SH.TRUSTED and s['heard'] == 'vowel']
    nah = [(w, s) for w, ss in sv.items() for s in ss if s['kind'] == 'nah' and s['rule'] in SH.TRUSTED and s['rule'] != 'final' and s['heard'] == 'none' and s['g1'] > s['g0'] >= 0]
    # (the phone ear's slot is a CTC spike, a frame or two inside the vowel: the whole vowel is the stretch between
    # the two consonants, so that is what goes — keeping 20 ms at each end for the consonants' own edges)
    for w, s in random.sample(na, min(2, len(na))):
        if s['g0'] < 0 or s['g1'] - s['g0'] < 3: continue
        a = int((s['g0'] + 1) * spf * SR); b = int((s['g1'] - 1) * spf * SR)
        if b - a < int(0.02 * SR): continue
        sv2, _ = probe(splice(x[:a], x[b:]), p['nikud']); s2 = slot(sv2, w, s['k'])
        if s2: feats.append({'case': 'drop', 'per': n, 'ps': i, 'w': w, 'k': s['k'], 'kind': s['kind'], 'rule': s['rule'], 'cut_ms': int((b - a) / SR * 1000), 'f': {k: s2[k] for k in ('used', 'mass', 'gapmax', 'used_any', 'mass_any', 'gapmax_any', 'heard')}})
        nr = SH.notes(sv2, None); nh = SH.notes(sv2, sv)
        C['drop tests'] += 1; C[f"drop heard {s2['heard'] if s2 else 'gone'}"] += 1
        C['drop caught (rules)'] += note_at(nr, w, s['k']); C['drop caught (hazzan)'] += note_at(nh, w, s['k'])
        C['drop collateral notes (hazzan)'] += others(nh, w, s['k'])
        rows.append({'case': 'drop', 'per': n, 'ps': i, 'w': w, 'k': s['k'], 'rule': s['rule'], 'before': s['mass'], 'after': s2 and s2['mass'], 'heard': s2 and s2['heard'], 'caught': note_at(nh, w, s['k'])})
    # add: put a short vowel (his own, from a na slot of this pasuk) into a silent shva
    donors = [s for w, s in na if s['g0'] >= 0 and (s['g1'] - s['g0'] - 2) * spf >= 0.04]
    for w, s in random.sample(nah, min(2, len(nah))) if donors else []:
        d = random.choice(donors); snip = x[int((d['g0'] + 1) * spf * SR):int((d['g1'] - 1) * spf * SR)].copy()
        at = int((s['g0'] + s['g1']) / 2 * spf * SR)
        sv3, _ = probe(splice(splice(x[:at], snip), x[at:]), p['nikud']); s3 = slot(sv3, w, s['k'])
        if s3: feats.append({'case': 'add', 'per': n, 'ps': i, 'w': w, 'k': s['k'], 'kind': s['kind'], 'rule': s['rule'], 'snip_ms': int(len(snip) / SR * 1000), 'f': {k: s3[k] for k in ('used', 'mass', 'gapmax', 'used_any', 'mass_any', 'gapmax_any', 'heard')}})
        nr = SH.notes(sv3, None); nh = SH.notes(sv3, sv)
        C['add tests'] += 1; C[f"add heard {s3['heard'] if s3 else 'gone'}"] += 1
        C['add caught (rules)'] += note_at(nr, w, s['k']); C['add caught (hazzan)'] += note_at(nh, w, s['k'])
        C['add collateral notes (hazzan)'] += others(nh, w, s['k'])
        rows.append({'case': 'add', 'per': n, 'ps': i, 'w': w, 'k': s['k'], 'rule': s['rule'], 'snip_ms': int(len(snip) / SR * 1000), 'gap_ms': int((s['g1'] - s['g0']) * spf * 1000), 'after': s3 and s3['mass'], 'heard': s3 and s3['heard'], 'caught': note_at(nh, w, s['k'])})
    done += 1
    if done % 20 == 0:
        print(f'{done} pesukim, {time.time() - t_start:.0f} s', dict(C), flush=True)
        json.dump({'counts': C, 'rows': rows, 'feats': feats}, open(os.path.join(HERE, 'shva_eval.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump({'counts': C, 'rows': rows, 'feats': feats}, open(os.path.join(HERE, 'shva_eval.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('\n'.join(f'{k}: {v}' for k, v in sorted(C.items())))
f = lambda a, b: f"{C[a]}/{C[b]} ({100 * C[a] / max(1, C[b]):.0f}%)"
print('\nfalse alarms on his own reading:', f('intact notes (false alarms)', 'intact slots (trusted)'), '· pesukim with one:', f('pesukim with a false alarm', 'pesukim'))
print('a dropped shva na caught:', 'rules', f('drop caught (rules)', 'drop tests'), '· against the hazzan', f('drop caught (hazzan)', 'drop tests'))
print('an added vowel caught:   ', 'rules', f('add caught (rules)', 'add tests'), '· against the hazzan', f('add caught (hazzan)', 'add tests'))
