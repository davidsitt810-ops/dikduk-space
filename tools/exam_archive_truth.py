"""The archive's 'right' takes are only as right as the site's sync events: a clip much shorter than the hazzan's own
line cannot hold it, and a clip whose line gap says 'not this line' probably does not either. This splits the right
takes into plausible and doubtful, and reports the rule's false alarms on the plausible ones."""
import json, os, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
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
T = json.load(open(os.path.join(HERE, 'exam_archive_takes.json'), encoding='utf-8')); R = json.load(open(os.path.join(HERE, 'exam_archive_rows.json'), encoding='utf-8'))
for t in T:
    if t.get('ref_dur') is None:
        s = LY[t['pid']]; recs = [f for f in s['t'] if len(sync_lines(t['pid'], f)) >= 3 and cached(f)]; A = s['b'] if s.get('b') in recs else recs[0]
        a, b = sync_lines(t['pid'], A)[t['line']]; t['ref_dur'] = round(b - a, 2)
def plausible(t): return 0.5 * t['ref_dur'] <= t['dur'] <= 2.0 * t['ref_dur'] and (t['gap'] is None or t['gap'] < 0.6)
right = [t for t in T if t['case'] == 'right']; ok = [t for t in right if plausible(t)]
print(f"right takes {len(right)}: plausible {len(ok)}, doubtful {len(right) - len(ok)}")
for label, group in (('plausible', ok), ('doubtful', [t for t in right if not plausible(t)])):
    marks = collections.Counter(m for t in group for m in t['marks'] if m); nw = sum(marks.values())
    print(f"  {label:9s} takes {len(group):3d} clean {sum(t['clean'] for t in group):3d} | words {nw}: red {marks['off']} ({100 * marks['off'] / max(1, nw):.1f}%), unsure {marks['unsure']} ({100 * marks['unsure'] / max(1, nw):.0f}%), ok {marks['ok']} ({100 * marks['ok'] / max(1, nw):.0f}%)")
print('\nred words on plausible right takes:')
key = lambda t: (t['case'], t['pid'], t['line'], t['rec'])
rows = collections.defaultdict(list)
for r in R: rows[(r['case'], r['pid'], r['line'], r['rec'])].append(r)
f = lambda v: 'None' if v is None else '%.2f' % v
for t in ok:
    if 'off' not in t['marks']: continue
    print(f"  {t['pid']} line {t['line'] + 1} {t['rec']}: dur {t['dur']} ref {t['ref_dur']} gap {f(t['gap'])} clean {t['clean']}")
    for r in sorted(rows[key(t)], key=lambda r: r['k']):
        print(f"     {r['w']:10s} {r['mark']:6s} n={r['n']} skel={f(r['skel'])} fit={f(r['fit'])} hskel={f(r['hskel'])} kept={r['kept']} pw={f(r['pw'])} drop={f(r['drop'])} why={r['why'] or ''}")
