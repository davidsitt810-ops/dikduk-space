"""Throat verdicts on Rabbi Alouf's intact held-out pesukim through the live local server, by letter and position."""
import json, os, sys, subprocess, collections, requests, random
HERE = os.path.dirname(os.path.abspath(__file__)); N = int(sys.argv[1]) if len(sys.argv) > 1 else 70
PER = [7, 12, 18, 21, 23, 32, 35, 40, 46, 94, 118, 123, 126, 140]
IDX = json.load(open(os.path.join(HERE, '..', 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))
random.seed(5); jobs = []
for n in PER:
    rec = IDX['perakim'][str(n)]
    for i, p in enumerate(rec['pesukim']):
        if p['t0'] is None or p['t1'] - p['t0'] > 14 or len(p['words']) < 4 or any(w['t0'] is None for w in p['words']): continue
        jobs.append((n, rec, i))
random.shuffle(jobs); jobs = jobs[:N]
cnt = collections.Counter(); heL = lambda w: [c for c in w if 'א' <= c <= 'ת']
for n, rec, i in jobs:
    p = rec['pesukim'][i]
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f"{p['t0'] - .2:.3f}", '-i', os.path.join(HERE, '..', 'alouf', 'mp3', rec['original']), '-t', f"{p['t1'] - p['t0'] + .4:.3f}", '-ac', '1', '-ar', '16000', '-f', 'wav', '-'], capture_output=True).stdout
    W = ' '.join(w.get('said', w['w']) for w in p['words'])
    j = requests.post('http://127.0.0.1:7861/check', params={'words': W}, data=out, headers={'content-type': 'audio/wav'}, timeout=600).json()
    for wd in j['take']['words']:
        L = heL(wd['w'])
        for th in wd['throat']:
            pos = 'start' if th['k'] == 0 else ('end' if th['k'] == len(L) - 1 else 'mid'); cnt[(th['c'], pos, th['v'])] += 1
for c in 'עח':
    for pos in ('start', 'mid', 'end'):
        tot = sum(v for (cc, pp, _), v in cnt.items() if cc == c and pp == pos)
        if tot: print(f"  {c} {pos:5s} n={tot:3d}: throat {cnt[(c, pos, 'throat')]} ({100 * cnt[(c, pos, 'throat')] / tot:.0f}%), unsure {cnt[(c, pos, 'unsure')]} ({100 * cnt[(c, pos, 'unsure')] / tot:.0f}%), plain {cnt[(c, pos, 'plain')]} ({100 * cnt[(c, pos, 'plain')] / tot:.0f}%)")
for c in 'עח':
    tot = sum(v for (cc, _, _), v in cnt.items() if cc == c); print(f"  {c} all n={tot}: throat {sum(v for (cc, _, vv), v in cnt.items() if cc == c and vv == 'throat')}, unsure {sum(v for (cc, _, vv), v in cnt.items() if cc == c and vv == 'unsure')}, plain {sum(v for (cc, _, vv), v in cnt.items() if cc == c and vv == 'plain')}")
