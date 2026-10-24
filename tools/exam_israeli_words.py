"""The words check on OTHER VOICES, clean read speech, no hazzan: 80 FLEURS he_il sentences (Israelis reading, held out
of every training set) checked against their own transcript (RIGHT), with one word cut out (SKIP) and two neighbours
swapped (SWAP) from the machine's own placement, and checked as another sentence's words (WRONG LINE). Through
app.analyse + app.summarize in process. Writes exam_israeli_rows.json / exam_israeli_takes.json and prints tallies."""
import sys, os, json, glob, time, random, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app
HERE = os.path.dirname(os.path.abspath(__file__)); random.seed(2); OUT = os.environ.get('EXAM_OUT', 'exam_israeli')
rows_meta = json.load(open(os.path.join(HERE, '..', 'fleurs', 'dev.json'), encoding='utf-8')); by = {r[1]: r[3] for r in rows_meta}
wavs = sorted(glob.glob(os.path.join(HERE, '..', 'fleurs_fresh', 'dev', '*.wav')))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 80
rows = []; takes = []; t0 = time.time(); n = 0
def check(x, W, alts=None):
    take, lp, spf = app.analyse(x, W, False, alts)
    for w in take['words']: w['pw'] = app.word_pw(w, None)
    out = {'words': W, 'take': take, 'vowel_names': app.VOWEL_NAME}
    return out, app.summarize(out)
def add(case, f, out, S, tampered):
    TW = out['take']['words']
    takes.append({'case': case, 'f': f, 'words': out['words'], 'marks': S['marks'], 'why': S['why'], 'clean': S['clean'], 'head': S.get('head'), 'gap': S['gap'], 'rival': (out['take'].get('rival') or {}).get('gain'), 'line_wrong': S['line_wrong'], 'cant_hear': S.get('cant_hear'), 'no_speech': S.get('no_speech'), 'dur': S['dur'], 'tampered': sorted(tampered), 'throat': S['throat'], 'nvow': len(S['vowels'])})
    for i, w in enumerate(TW):
        rows.append({'case': case, 'f': f, 'k': i, 'bad': 1 if i in tampered else 0, 'w': w['w'], 'n': w['n'], 'skel': w['skel'], 'fit': None, 'hskel': w.get('hskel'), 'vskel': w.get('vskel'), 'kept': w.get('kept'), 'pw': w.get('pw'), 'drop': w.get('drop'), 'swap': w.get('swap'), 'gap': out['take'].get('gap'), 'rival': (out['take'].get('rival') or {}).get('gain'), 'clean': S['clean'], 'mark': S['marks'][i], 'why': S['why'][i], 'dur': round(w['t1'] - w['t0'], 3)})
texts = [(os.path.basename(w), by.get(os.path.basename(w))) for w in wavs]
for w in wavs:
    f = os.path.basename(w); text = by.get(f)
    if not text: continue
    W = app.he_words(text)
    if len(W) < 4: continue
    x = app.decode_audio(open(w, 'rb').read())
    alts = random.sample([t for g, t in texts if t and g != f], 5); altW = [app.he_words(t) for t in alts]
    try: out, S = check(x, W, altW)
    except Exception as e: print('fail', f, e, flush=True); continue
    add('right', f, out, S, set()); TW = out['take']['words']; wt = [(t['t0'], t['t1']) for t in TW]
    # skip a word the machine placed with some width
    cands = [i for i in range(1, len(W) - 1) if (TW[i]['n'] or 0) >= 2 and wt[i][1] > wt[i][0] + .15]
    if cands:
        i = random.choice(cands); a, b = wt[i]; xs = np.concatenate([x[:int(a * app.SR)], x[int(b * app.SR):]])
        try: o2, S2 = check(xs, W, altW); add('skip', f, o2, S2, {i})
        except Exception as e: print('skip fail', f, e, flush=True)
    cands = [i for i in range(0, len(W) - 1) if (TW[i]['n'] or 0) >= 2 and (TW[i + 1]['n'] or 0) >= 2 and wt[i][1] <= wt[i + 1][0] + 1e-3 and wt[i][1] > wt[i][0] + .15 and wt[i + 1][1] > wt[i + 1][0] + .15]
    if cands:
        i = random.choice(cands); (a1, b1), (a2, b2) = wt[i], wt[i + 1]; sr = app.SR
        xs = np.concatenate([x[:int(a1 * sr)], x[int(a2 * sr):int(b2 * sr)], x[int(b1 * sr):int(a2 * sr)], x[int(a1 * sr):int(b1 * sr)], x[int(b2 * sr):]])
        try: o3, S3 = check(xs, W, altW); add('swap', f, o3, S3, {i, i + 1})
        except Exception as e: print('swap fail', f, e, flush=True)
    # the same audio as another sentence's words
    other = random.choice([t for g, t in texts if t and g != f and abs(len(app.he_words(t)) - len(W)) <= 2] or [None])
    if other:
        Wo = app.he_words(other)
        try: o4, S4 = check(x, Wo, altW[:4] + [W]); add('wrongline', f, o4, S4, set(range(len(Wo))))
        except Exception as e: print('wrongline fail', f, e, flush=True)
    n += 1
    if n % 10 == 0:
        print(f'{n} sentences · {int(time.time() - t0)} s · takes {len(takes)}', flush=True)
        json.dump(rows, open(os.path.join(HERE, OUT + '_rows.json'), 'w'), ensure_ascii=False); json.dump(takes, open(os.path.join(HERE, OUT + '_takes.json'), 'w'), ensure_ascii=False)
    if n >= N: break
json.dump(rows, open(os.path.join(HERE, OUT + '_rows.json'), 'w'), ensure_ascii=False); json.dump(takes, open(os.path.join(HERE, OUT + '_takes.json'), 'w'), ensure_ascii=False)
print('done', n, 'sentences', len(rows), 'rows', len(takes), 'takes', int(time.time() - t0), 's')
for case in ('right', 'skip', 'swap', 'wrongline'):
    T = [t for t in takes if t['case'] == case]; R = [r for r in rows if r['case'] == case and (r['n'] or 0) >= 1]
    if not T: continue
    good = [r for r in R if not r['bad']]; bad = [r for r in R if r['bad']]; g = collections.Counter(r['mark'] for r in good); b = collections.Counter(r['mark'] for r in bad)
    s = f"  {case:9s} takes {len(T):3d} (clean {sum(bool(t['clean']) for t in T)}, line-wrong {sum(bool(t['line_wrong']) for t in T)}, cannot-hear {sum(bool(t['cant_hear']) for t in T)}, no-speech {sum(bool(t['no_speech']) for t in T)})"
    if good: s += f" | right words {len(good):4d}: red {g['off']} ({100 * g['off'] / len(good):.1f}%), unsure {g['unsure']} ({100 * g['unsure'] / len(good):.0f}%)"
    if bad: s += f" | wrong words {len(bad):4d}: caught {b['off']} ({100 * b['off'] / len(bad):.0f}%), unsure {b['unsure']} ({100 * b['unsure'] / len(bad):.0f}%), passed {b['ok'] + b['']} ({100 * (b['ok'] + b['']) / len(bad):.0f}%)"
    print(s)
heads = sorted(t['head'] for t in takes if t['case'] == 'right' and t['head'] is not None)
print('right takes head median p10/p50/p90:', np.percentile(heads, 10), np.percentile(heads, 50), np.percentile(heads, 90))
th = collections.Counter((x['c'], x.get('raw') or x['v']) for t in takes if t['case'] == 'right' for x in t['throat']); print('throat verdicts (raw) on Israeli right takes:', dict(th))
print('vowel notes on right takes:', sum(t['nvow'] for t in takes if t['case'] == 'right'), 'words', sum(len(t['words']) for t in takes if t['case'] == 'right'))
