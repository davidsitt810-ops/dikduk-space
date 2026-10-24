"""The pizmonim exam: the site's own archive, where a pizmon has two or more synced recordings. Hazzan A's line is
the reference (as on the site); hazzan B's line k is a RIGHT take (another voice, often with instruments), checked
word by word with the server's own verdict (app.summarize: marks, why, line_wrong, clean, throat). The same take is
also checked as line j of the same pizmon (WRONG LINE), and, where B's take is clean, with one of its words cut out
(SKIP, the word's span taken from the machine's own placement) and with two neighbours swapped (SWAP).
Writes exam_archive_rows.json (one row per word) and prints the tallies. usage: exam_archive.py [max pizmonim] [max lines]"""
import sys, os, json, time, random, hashlib, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'space'))
os.environ.setdefault('DK_NO_WARM', '1')
import numpy as np
import app
HERE = os.path.dirname(os.path.abspath(__file__)); random.seed(3)
NP = int(sys.argv[1]) if len(sys.argv) > 1 else 15; MAXL = int(sys.argv[2]) if len(sys.argv) > 2 else 4
LY = json.load(open(os.path.join(HERE, '..', 'lyrics_full.json'), encoding='utf-8'))['s']
cache = set(os.listdir(os.path.join(HERE, '..', 'dkcache')))
def cached(f): return ('mp3_' + hashlib.sha1(f.encode()).hexdigest()) in cache
def sync_lines(pid, f):
    ev = [tuple(map(int, x.split(','))) for x in LY[pid]['t'][f].split(';') if x]; out = {}
    for i, (t, k) in enumerate(ev):
        if k < 0 or k in out: continue
        t1 = ev[i + 1][0] / 10 if i + 1 < len(ev) else t / 10 + 8
        if 1.5 <= t1 - t / 10 <= 25: out[k] = (t / 10, t1)
    return out
AUDIO = {}
def audio(f):
    if f not in AUDIO: AUDIO[f] = app.decode_audio(app.fetch_archive(f))
    return AUDIO[f]
# the pizmonim the letter head was trained on (manifest.jsonl 'ar' rows) are marked, so the tallies can be split
seen = set()
try:
    for l in open(os.path.join(HERE, 'manifest.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        if r.get('src') == 'ar': seen.add(str(r.get('pid')))
except Exception: pass
pairs = []
for pid, s in LY.items():
    if not s.get('t'): continue
    recs = [f for f in s['t'] if len(sync_lines(pid, f)) >= 3 and cached(f)]
    if len(recs) >= 2: pairs.append(pid)
pairs = pairs[:NP]
print(f'{len(pairs)} pizmonim with 2+ synced recordings in the cache; trained-on: {sorted(p for p in pairs if p in seen)}', flush=True)
rows = []; takes = []; t_start = time.time(); n_takes = 0
# resume: pizmonim already in the files from an earlier run are kept and skipped
if os.environ.get('RESUME') and os.path.exists(os.path.join(HERE, 'exam_archive_takes.json')):
    rows = json.load(open(os.path.join(HERE, 'exam_archive_rows.json'), encoding='utf-8')); takes = json.load(open(os.path.join(HERE, 'exam_archive_takes.json'), encoding='utf-8'))
    done_pids = set(t['pid'] for t in takes); n_takes = len(takes); pairs = [p for p in pairs if p not in done_pids]
    print(f'resuming: {len(done_pids)} pizmonim done, {len(pairs)} to go', flush=True)
ALTS = {}   # pid -> all its lines as word lists
def check(x, W, R, pid=None):
    alts = [a for a in ALTS.get(pid, []) if a != W]
    take, lp, spf = app.analyse(x, W, False, alts)
    for w in take['words']: w['pw'] = app.word_pw(w, None)
    out = {'words': W, 'take': take, 'ref': R, 'fit': app.fit_against(lp, spf, R['words'])}
    if app.FULL is not None or app.FT is not None:
        out['vowels'] = app.compare_vowels({i: w.get('vow', []) for i, w in enumerate(take['words'])}, {i: w.get('vow', []) for i, w in enumerate(R['words'])})
    out['vowel_names'] = app.VOWEL_NAME
    return out, app.summarize(out)
def add(case, pid, B, k, out, S, tampered, extra=None):
    global n_takes
    n_takes += 1; TW = out['take']['words']; F = out.get('fit') or []
    takes.append({'case': case, 'pid': pid, 'rec': B, 'line': k, 'seen': pid in seen, 'clean': S['clean'], 'gap': S['gap'], 'rival': (out['take'].get('rival') or {}).get('gain'), 'rival_head': (out['take'].get('rival') or {}).get('head'), 'line_wrong': S['line_wrong'], 'marks': S['marks'], 'why': S['why'], 'words': out['words'], 'tampered': sorted(tampered), 'dur': S['dur'], 'ref_dur': out['ref'].get('dur'), 'nvow': len(S['vowels']), 'throat': S['throat'], **(extra or {})})
    for i, w in enumerate(TW):
        f = F[i] if i < len(F) else {}
        rows.append({'case': case, 'pid': pid, 'rec': B, 'line': k, 'k': i, 'seen': pid in seen, 'bad': 1 if i in tampered else 0, 'w': w['w'], 'n': w['n'], 'skel': w['skel'], 'fit': f.get('fit'), 'hskel': w.get('hskel'), 'vskel': w.get('vskel'), 'kept': w.get('kept'), 'pw': w.get('pw'),
                     'drop': w.get('drop'), 'swap': w.get('swap'), 'gap': out['take'].get('gap'), 'rival': (out['take'].get('rival') or {}).get('gain'), 'rival_head': (out['take'].get('rival') or {}).get('head'), 'clean': S['clean'], 'mark': S['marks'][i], 'why': S['why'][i], 'line_wrong': S['line_wrong'], 'selffit': (out['ref']['words'][i].get('selffit') if i < len(out['ref']['words']) else None), 'dur': round(w['t1'] - w['t0'], 3)})
for pid in pairs:
    s = LY[pid]; recs = [f for f in s['t'] if len(sync_lines(pid, f)) >= 3 and cached(f)]
    ALTS[pid] = [app.he_words(l) for l in s['l'] if app.he_words(l)]
    A = s['b'] if s.get('b') in recs else recs[0]; others = [f for f in recs if f != A][:2]
    linesA = sync_lines(pid, A); refs = {}
    ks = [k for k in sorted(linesA) if k < len(s['l']) and any(k in sync_lines(pid, B) for B in others)]   # lines both hazzanim sang
    for k in ks[:MAXL]:
        W = app.he_words(s['l'][k])
        if len(W) < 3: continue
        try: refs[k] = app.ref_line(A, *linesA[k], W)
        except Exception as e: print('ref fail', pid, A, k, e, flush=True)
    for B in others:
        linesB = sync_lines(pid, B)
        for k in refs:
            if k not in linesB: continue
            t0, t1 = linesB[k]; x = audio(B)[int(t0 * app.SR):int(t1 * app.SR)]
            if x.shape[0] < app.SR: continue
            W = app.he_words(s['l'][k])
            try: out, S = check(x, W, refs[k], pid)
            except Exception as e: print('check fail', pid, B, k, e, flush=True); continue
            add('right', pid, B, k, out, S, set())
            TW = out['take']['words']
            # wrong line: the same take as another line of the pizmon (different words)
            js = [j for j in refs if j != k and app.he_words(s['l'][j]) != W]
            if js:
                j = random.choice(js); Wj = app.he_words(s['l'][j])
                try: outj, Sj = check(x, Wj, refs[j], pid); add('wrongline', pid, B, j, outj, Sj, set(range(len(Wj))), {'sung': k})
                except Exception as e: print('wrongline fail', pid, B, k, e, flush=True)
            # tampering only where the machine placed the words with some confidence (a clean take)
            if S['clean'] and len(W) >= 4:
                wt = [(w['t0'], w['t1']) for w in TW]
                cands = [i for i in range(1, len(W) - 1) if (TW[i]['n'] or 0) >= 2 and wt[i][1] > wt[i][0] + .15]
                if cands:
                    i = random.choice(cands); a, b = wt[i]
                    xs = np.concatenate([x[:int(a * app.SR)], x[int(b * app.SR):]])
                    try: outs, Ss = check(xs, W, refs[k], pid); add('skip', pid, B, k, outs, Ss, {i})
                    except Exception as e: print('skip fail', pid, B, k, e, flush=True)
                cands = [i for i in range(0, len(W) - 1) if (TW[i]['n'] or 0) >= 2 and (TW[i + 1]['n'] or 0) >= 2 and wt[i][1] <= wt[i + 1][0] + 1e-3 and wt[i][1] > wt[i][0] + .15 and wt[i + 1][1] > wt[i + 1][0] + .15]
                if cands:
                    i = random.choice(cands); (a1, b1), (a2, b2) = wt[i], wt[i + 1]; sr = app.SR
                    xs = np.concatenate([x[:int(a1 * sr)], x[int(a2 * sr):int(b2 * sr)], x[int(b1 * sr):int(a2 * sr)], x[int(a1 * sr):int(b1 * sr)], x[int(b2 * sr):]])
                    try: outw, Sw = check(xs, W, refs[k], pid); add('swap', pid, B, k, outw, Sw, {i, i + 1})
                    except Exception as e: print('swap fail', pid, B, k, e, flush=True)
    print(f'{pid}: {A} + {others} lines {list(refs)} · takes {n_takes} · {int(time.time() - t_start)} s', flush=True)
    json.dump(rows, open(os.path.join(HERE, 'exam_archive_rows.json'), 'w'), ensure_ascii=False); json.dump(takes, open(os.path.join(HERE, 'exam_archive_takes.json'), 'w'), ensure_ascii=False)
json.dump(rows, open(os.path.join(HERE, 'exam_archive_rows.json'), 'w'), ensure_ascii=False); json.dump(takes, open(os.path.join(HERE, 'exam_archive_takes.json'), 'w'), ensure_ascii=False)
print('done', len(rows), 'rows', n_takes, 'takes', int(time.time() - t_start), 's')
# ---- tallies
def tally(rows, takes, label):
    print(f'\n== {label}: {len(takes)} takes')
    for case in ('right', 'skip', 'swap', 'wrongline'):
        T = [t for t in takes if t['case'] == case]; R = [r for r in rows if r['case'] == case and (r['n'] or 0) >= 1]
        if not T: continue
        good = [r for r in R if not r['bad']]; bad = [r for r in R if r['bad']]
        g = collections.Counter(r['mark'] for r in good); b = collections.Counter(r['mark'] for r in bad)
        s = f"  {case:9s} takes {len(T):3d} (clean {sum(t['clean'] for t in T)}, line-wrong {sum(bool(t['line_wrong']) for t in T)})"
        if good: s += f" | right words {len(good):4d}: red {g['off']} ({100 * g['off'] / len(good):.1f}%), unsure {g['unsure']} ({100 * g['unsure'] / len(good):.0f}%)"
        if bad: s += f" | wrong words {len(bad):4d}: caught {b['off']} ({100 * b['off'] / len(bad):.0f}%), unsure {b['unsure']} ({100 * b['unsure'] / len(bad):.0f}%), passed {b['ok'] + b['']} ({100 * (b['ok'] + b['']) / len(bad):.0f}%)"
        print(s)
tally(rows, takes, 'all')
tally([r for r in rows if not r['seen']], [t for t in takes if not t['seen']], 'pizmonim the heads never saw')
fa = [(r['pid'], r['line'], r['w'], r['why'], round(r['skel'], 2), r['fit'] and round(r['fit'], 2), r['kept'], r['pw'] and round(r['pw'], 2), r['drop'] and round(r['drop'], 1)) for r in rows if r['case'] in ('right', 'skip', 'swap') and not r['bad'] and r['mark'] == 'off']
print('\nfalse alarms (right words marked red):', len(fa))
for x in fa: print('  ', x)
th = collections.Counter((t['case'] == 'right', x['c'], x['v']) for t in takes for x in t['throat'] if t['case'] == 'right')
print('\nthroat verdicts on right takes:', {f'{c} {v}': n for (_, c, v), n in sorted(th.items())})
