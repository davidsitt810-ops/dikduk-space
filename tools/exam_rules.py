"""Reads exam_rows.json / exam_lines.json (exam_alouf.py) and answers: how does the shipped word rule do on clean
reading, what do the new whole-line signals (drop / swap gains, line gap) add, and which thresholds keep false
alarms under 1% while catching more. Also the throat-verdict and vowel-note rates on the intact pesukim.
usage: exam_rules.py [exam_rows.json] [exam_lines.json]"""
import sys, os, json, itertools, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'exam_rows.json')))
L = json.load(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'exam_lines.json')))
print(f'{len(R)} word rows, {len(L)} intact pesukim; cases: {collections.Counter(r["case"] for r in R)}')

def mark_old(r):
    """the shipped rule (static/index.html markOf)"""
    n = r['n'] or 0; sk = r['skel']; ft = r['fit']; kp = r['kept']; pw = r['pw']; clean = r['clean']; hs = r.get('hskel')
    if not n or sk is None: return ''
    sure = clean and kp is not None and kp >= .75 and hs is not None and hs >= .6 and (pw is None or pw < .8)
    if n >= 2:
        if sk < .2 and (ft is None or ft < .15):
            if ft is None and clean and not (kp is not None and kp < .75): return 'unsure'
            return 'off'
        if clean and pw is not None and pw >= .95: return 'off'
        if sure: return 'ok'
        if sk < .4 or (ft is not None and ft < .2) or (kp is not None and kp < .5) or (pw is not None and pw >= .8): return 'unsure'
        return 'ok'
    return 'unsure' if sk < .2 and not sure else 'ok'

def swap_max(r, rows_of_line):
    """the swap gain of the pair this word belongs to (with the previous or the next word), the larger one"""
    k = r['k']; g = []
    if r.get('swap') is not None: g.append(r['swap'])
    if k > 0:
        prev = rows_of_line.get(k - 1)
        if prev and prev.get('swap') is not None: g.append(prev['swap'])
    return max(g) if g else None

# group rows by line (case, per, ps)
lines = collections.defaultdict(dict)
for r in R: lines[(r['case'], r['per'], r['ps'])][r['k']] = r
for r in R: r['swapmax'] = swap_max(r, lines[(r['case'], r['per'], r['ps'])])

def mark_new(r, D=10.0, S=10.0, G=0.35, use_gap=True):
    """the shipped rule plus the whole-line evidence (only on a clean take, as the head's other signals)"""
    m = mark_old(r)
    if not r['clean'] or (r['n'] or 0) < 2: return m
    if r.get('drop') is not None and r['drop'] >= D: return 'off'
    if r.get('swapmax') is not None and r['swapmax'] >= S: return 'off'
    if use_gap and r.get('gap') is not None and r['gap'] >= G and m == 'ok': return 'unsure'
    return m

def report(name, fn):
    out = {}
    for case in ('intact', 'skip', 'swap', 'wrongword', 'wrongline'):
        rows = [r for r in R if r['case'] == case and (r['n'] or 0) >= 1]
        if not rows: continue
        good = [r for r in rows if not r['bad']]; bad = [r for r in rows if r['bad']]
        mg = collections.Counter(fn(r) for r in good); mb = collections.Counter(fn(r) for r in bad)
        out[case] = (len(good), mg, len(bad), mb)
    print(f'\n{name}')
    for case, (ng, mg, nb, mb) in out.items():
        s = f'  {case:10s} right words {ng:4d}: red {mg["off"]} ({100 * mg["off"] / max(1, ng):.1f}%), unsure {mg["unsure"]} ({100 * mg["unsure"] / max(1, ng):.0f}%)'
        if nb: s += f' | wrong words {nb:3d}: caught {mb["off"]} ({100 * mb["off"] / nb:.0f}%), unsure {mb["unsure"]} ({100 * mb["unsure"] / nb:.0f}%), passed {mb["ok"] + mb[""]} ({100 * (mb["ok"] + mb[""]) / nb:.0f}%)'
        print(s)
    return out

report('SHIPPED RULE (skel / fit / kept / pw, clean gate)', mark_old)
# what the new signals look like, right words vs wrong words
for sig in ('drop', 'drop_ph', 'swapmax', 'gap', 'gap_ph'):
    good = [r[sig] for r in R if not r['bad'] and r.get(sig) is not None and r['case'] != 'wrongline']
    for case in ('skip', 'swap', 'wrongword', 'wrongline'):
        bad = [r[sig] for r in R if r['bad'] and r['case'] == case and r.get(sig) is not None]
        if bad: print(f'{sig:8s} right: p50 {np.percentile(good, 50):7.2f} p99 {np.percentile(good, 99):7.2f} max {max(good):7.2f} | wrong ({case}): p10 {np.percentile(bad, 10):7.2f} p50 {np.percentile(bad, 50):7.2f}')
# thresholds: false alarms on right words (all cases but wrongline) under 1%, best catch
good = [r for r in R if not r['bad'] and r['case'] != 'wrongline' and (r['n'] or 0) >= 2]
bad = [r for r in R if r['bad'] and (r['n'] or 0) >= 2]
best = None
for D in (6, 8, 10, 12, 15, 20, 25):
    for S in (6, 8, 10, 12, 15, 20, 25):
        for G in (0.25, 0.3, 0.35, 0.4, 0.5, 9):
            fa = sum(mark_new(r, D, S, G) == 'off' for r in good) / len(good)
            caught = sum(mark_new(r, D, S, G) == 'off' for r in bad) / len(bad)
            uns = sum(mark_new(r, D, S, G) == 'unsure' for r in good) / len(good)
            if fa <= 0.01 and (best is None or caught > best[0] or (caught == best[0] and uns < best[4])): best = (caught, D, S, G, uns, fa)
print(f'\nbest thresholds with false alarms <= 1%: drop >= {best[1]}, swap >= {best[2]}, gap >= {best[3]} -> catches {100 * best[0]:.0f}% of wrong words, false alarms {100 * best[5]:.2f}%, right words unsure {100 * best[4]:.1f}%')
report(f'NEW RULE (drop >= {best[1]}, swap >= {best[2]}, gap >= {best[3]})', lambda r: mark_new(r, best[1], best[2], best[3]))
# the line gap as a "this is not that line" meter
gi = [l['gap'] for l in L if l['gap'] is not None]; gw = [r['gap'] for r in R if r['case'] == 'wrongline' and r['k'] == 0 and r['gap'] is not None]
gs = [r['gap'] for r in R if r['case'] == 'skip' and r['k'] == 0 and r['gap'] is not None]
print(f'\nLINE GAP (head, nats/frame): intact p50 {np.median(gi):.3f} p95 {np.percentile(gi, 95):.3f} max {max(gi):.3f} | one word skipped p50 {np.median(gs):.3f} | wrong line p05 {np.percentile(gw, 5):.3f} p50 {np.median(gw):.3f}')
# throat verdicts on intact pesukim, by position (Rabbi Alouf: register says ayin pharyngeal start 91 / mid 83 / end 47 %, het 99 %)
th = collections.Counter();
for l in L:
    for t in l['throat']: th[(t['c'], t['pos'], t['v'])] += 1
print('\nTHROAT VERDICTS on intact pesukim (c, position -> throat / unsure / plain):')
for c in 'עח':
    for pos in ('start', 'mid', 'end'):
        n = sum(v for (cc, pp, _), v in th.items() if cc == c and pp == pos)
        if n: print(f'  {c} {pos:5s} n={n:3d}: throat {th[(c, pos, "throat")]} ({100 * th[(c, pos, "throat")] / n:.0f}%), unsure {th[(c, pos, "unsure")]} ({100 * th[(c, pos, "unsure")] / n:.0f}%), plain {th[(c, pos, "plain")]} ({100 * th[(c, pos, "plain")] / n:.0f}%)')
# vowel notes against the nikud on intact pesukim (he reads right: every note is a false alarm, give or take a kamatz katan)
nv = sum(l['nvow'] for l in L); notes = sum(len(v) for l in L if isinstance(l['vowel_notes'], dict) for v in l['vowel_notes'].values())
pairs = collections.Counter((d['you'], d['ref']) for l in L if isinstance(l['vowel_notes'], dict) for v in l['vowel_notes'].values() for d in v)
print(f'\nVOWELS vs nikud on intact pesukim: {notes} notes over {nv} vowel slots ({100 * notes / max(1, nv):.1f}%); most common (you, nikud): {pairs.most_common(6)}')
ms = [l['ms'] for l in L]; print(f'\nanalysis time per pasuk: median {np.median(ms) / 1000:.1f} s for {np.median([l["dur"] for l in L]):.1f} s of audio')

# ---- refinements: drop as a winner-take-all signal (only the line's largest drop may flag, and only when it stands
# well above the second), the line gap as a line verdict
def drop_rank(r):
    rows = lines[(r['case'], r['per'], r['ps'])]; ds = sorted((x['drop'] for x in rows.values() if x.get('drop') is not None), reverse=True)
    if r.get('drop') is None or not ds: return None, None
    second = ds[1] if len(ds) > 1 else -1e9
    return r['drop'] == ds[0], second
def mark_v2(r, D=15.0, S=10.0, G=0.5, margin=8.0):
    m = mark_old(r)
    if not r['clean'] or (r['n'] or 0) < 2: return m
    top, second = drop_rank(r)
    if r.get('drop') is not None and top and r['drop'] >= D and r['drop'] - second >= margin: return 'off'
    if r.get('swapmax') is not None and r['swapmax'] >= S: return 'off'
    if r.get('gap') is not None and r['gap'] >= G and m == 'ok': return 'unsure'
    return m
best2 = None
for D in (8, 10, 12, 15, 20, 25):
    for S in (6, 8, 10, 12, 15):
        for margin in (0, 4, 8, 12):
            fa = sum(mark_v2(r, D, S, 0.5, margin) == 'off' for r in good) / len(good); caught = sum(mark_v2(r, D, S, 0.5, margin) == 'off' for r in bad) / len(bad)
            if fa <= 0.01 and (best2 is None or caught > best2[0]): best2 = (caught, D, S, margin, fa)
print(f'\nwinner-take-all drop: best with FA <= 1%: drop >= {best2[1]} (and >= second + {best2[3]}), swap >= {best2[2]} -> catches {100 * best2[0]:.0f}%, FA {100 * best2[4]:.2f}%')
report(f'RULE v2 (top drop >= {best2[1]} by {best2[3]}, swap >= {best2[2]}, gap >= 0.5 -> unsure)', lambda r: mark_v2(r, best2[1], best2[2], 0.5, best2[3]))
# the line gap as a line verdict
gi_all = [(l['gap'], 'intact') for l in L if l['gap'] is not None]
for case in ('skip', 'swap', 'wrongword', 'wrongline'):
    gi_all += [(r['gap'], case) for r in R if r['case'] == case and r['k'] == 0 and r['gap'] is not None]
for G in (0.3, 0.4, 0.5, 0.6, 0.8):
    print(f'line gap >= {G}: ' + ', '.join(f'{case} {100 * np.mean([g >= G for g, c in gi_all if c == case]):.0f}%' for case in ('intact', 'skip', 'swap', 'wrongword', 'wrongline')))

# ---- final candidate: swaps winner-take-all too (one pair per line), drop winner-take-all with a margin, gap 0.6
def line_marks(key, D, M, S, G):
    rows = lines[key]; ks = sorted(rows); TW = [rows[k] for k in ks]
    marks = {k: mark_old(rows[k]) for k in ks}; why = {}
    if not TW or not TW[0]['clean']: return marks, why, False
    ds = [r['drop'] if r.get('drop') is not None else -1e9 for r in TW]; top = int(np.argmax(ds)); second = max([d for i, d in enumerate(ds) if i != top], default=-1e9)
    if (TW[top]['n'] or 0) >= 2 and ds[top] >= D and ds[top] - second >= M: marks[ks[top]] = 'off'; why[ks[top]] = 'dropped'
    sw = [r['swap'] if r.get('swap') is not None else -1e9 for r in TW[:-1]]
    if sw:
        j = int(np.argmax(sw))
        if sw[j] >= S and (TW[j]['n'] or 0) >= 2 and (TW[j + 1]['n'] or 0) >= 2: marks[ks[j]] = marks[ks[j + 1]] = 'off'; why[ks[j]] = why[ks[j + 1]] = 'swapped'
    lw = TW[0].get('gap') is not None and TW[0]['gap'] >= G
    if lw: marks = {k: ('unsure' if m == 'ok' else m) for k, m in marks.items()}
    return marks, why, lw
def eval_final(D, M, S, G, show=False):
    res = {}
    for key in lines:
        marks, why, lw = line_marks(key, D, M, S, G)
        for k, r in lines[key].items():
            if (r['n'] or 0) < 1: continue
            c = res.setdefault(r['case'], {'good': collections.Counter(), 'bad': collections.Counter(), 'ng': 0, 'nb': 0})
            if r['bad']: c['bad'][marks[k]] += 1; c['nb'] += 1
            else: c['good'][marks[k]] += 1; c['ng'] += 1
    fa = sum(c['good']['off'] for k, c in res.items() if k != 'wrongline'); ng = sum(c['ng'] for k, c in res.items() if k != 'wrongline')
    caught = sum(c['bad']['off'] for c in res.values()); nb = sum(c['nb'] for c in res.values())
    if show:
        print(f'\nFINAL RULE: top drop >= {D} (margin {M}), top swap >= {S}, line gap >= {G}')
        for case, c in res.items():
            s = f'  {case:10s} right {c["ng"]:4d}: red {c["good"]["off"]} ({100 * c["good"]["off"] / max(1, c["ng"]):.1f}%), unsure {c["good"]["unsure"]} ({100 * c["good"]["unsure"] / max(1, c["ng"]):.0f}%)'
            if c['nb']: s += f' | wrong {c["nb"]:3d}: caught {c["bad"]["off"]} ({100 * c["bad"]["off"] / c["nb"]:.0f}%), unsure {c["bad"]["unsure"]} ({100 * c["bad"]["unsure"] / c["nb"]:.0f}%), passed {c["bad"]["ok"] + c["bad"][""]} ({100 * (c["bad"]["ok"] + c["bad"][""]) / c["nb"]:.0f}%)'
            print(s)
    return fa, ng, caught, nb
print('\nsweep (false alarms on right words of all cases but wrongline / catches of wrong words, wrongline excluded from catches):')
for D, M, S in itertools.product((8, 10, 12, 15), (0, 4, 8), (6, 8, 10, 12)):
    fa, ng, caught, nb = eval_final(D, M, S, 0.6)
    wl = sum(1 for key in lines if key[0] == 'wrongline')
    c2 = sum(line_marks(key, D, M, S, 0.6)[0][k] == 'off' for key in lines if key[0] != 'wrongline' for k, r in lines[key].items() if r['bad'])
    nb2 = sum(1 for key in lines if key[0] != 'wrongline' for k, r in lines[key].items() if r['bad'])
    print(f'  D {D:2d} M {M} S {S:2d}: FA {fa:2d}/{ng} ({100 * fa / ng:.2f}%)  catches {c2}/{nb2} ({100 * c2 / nb2:.0f}%)')
eval_final(10, 4, 8, 0.6, show=True)
eval_final(12, 6, 10, 0.6, show=True)
