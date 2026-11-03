"""Haftarot with two candidate passages: the right one keeps ~all its verses, the wrong one should keep none — but a
few verses of a wrong text can pass the cutter's filter by chance. Drop every item of a losing candidate (when the
winner kept at least half its verses), from the manifest and the features. usage: drop_losers.py [--go]"""
import json, os, sys, collections, shutil
S = '/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad'; L = f'{S}/voices/lt'
MAN = f'{S}/space_test/manifest_voices.jsonl'; FEAT = f'{S}/space_test/feat'
rows = [l.rstrip('\n').split('\t') for l in open(f'{L}/bundle/haftarot.tsv', encoding='utf-8')]
kept = collections.Counter()
lines = open(MAN, encoding='utf-8').read().splitlines()
for l in lines:
    if '"voice": "lthaf"' in l: kept[json.loads(l)['pid']] += 1
cand = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, []]))   # file -> candidate -> [kept, verses, pids]
for f, name, ref, bk, nv, bt in rows:
    t = json.load(open(f'{L}/bundle/texts/{bt.rstrip("_")}.json', encoding='utf-8'))
    tag = bt.rstrip('_').rstrip('0123456789'); c = cand[f][tag]   # parts of one passage (Hosea + Micah) share a candidate
    pids = [f'lthaf_{bt}{ch}' for ch in t]
    c[0] += sum(kept[p] for p in pids); c[1] += int(nv); c[2] += pids
drop = set()
for f, cs in cand.items():
    if len(cs) < 2: continue
    win = max(cs, key=lambda k: cs[k][0] / max(1, cs[k][1]))
    if cs[win][0] < .5 * cs[win][1]: continue
    for k, (kk, nv, pids) in cs.items():
        if k != win and kk: drop |= set(pids); print(f'{os.path.basename(f)}: drop {kk} items of {k} (winner {win}: {cs[win][0]}/{cs[win][1]})')
ids = [json.loads(l)['id'] for l in lines if '"voice": "lthaf"' in l and json.loads(l)['pid'] in drop]
print(len(ids), 'items to drop')
if '--go' in sys.argv and ids:
    shutil.copy(MAN, MAN + '.before_drop_losers')
    keep = [l for l in lines if not ('"voice": "lthaf"' in l and json.loads(l)['pid'] in drop)]
    open(MAN, 'w', encoding='utf-8').write('\n'.join(keep) + '\n')
    for i in ids:
        p = os.path.join(FEAT, i + '.npz')
        if os.path.exists(p): os.remove(p)
    print('dropped; manifest', len(lines), '->', len(keep), 'lines')
