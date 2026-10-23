"""The false-alarm test for the throat ear: Israeli Hebrew speech (FLEURS he_il, read by Israelis) where ע is said like
א and ח like כ. Every ע/ח in ~60 sentences goes through the live local server (/check with the sentence as the
words). A good judge says "plain" or "unsure" here and almost never "throat". Also: the words check on clean
read speech (skel of right words)."""
import json, os, sys, glob, time, requests, collections
rows = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'fleurs', 'dev.json'), encoding='utf-8'))
by = {r[1]: r[2] for r in rows}
wavs = sorted(glob.glob(os.path.join(os.path.dirname(__file__), '..', 'fleurs_fresh', 'dev', '*.wav')))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
cnt = collections.Counter(); het = collections.Counter(); skels = []; t0 = time.time(); n = 0
for w in wavs:
    text = by.get(os.path.basename(w))
    if not text or not any(c in text for c in 'עח'): continue
    r = requests.post('http://127.0.0.1:7861/check', params={'words': text}, data=open(w, 'rb').read(), headers={'content-type': 'audio/wav'}, timeout=300)
    j = r.json()
    if 'err' in j: print('err', j); continue
    for wd in j['take']['words']:
        if wd['skel'] is not None and wd['n'] >= 2: skels.append(wd['skel'])
        for th in wd['throat']:
            (cnt if th['c'] == 'ע' else het)[th['v']] += 1
    n += 1
    if n >= N: break
print(f'{n} Israeli sentences, {int(time.time() - t0)} s')
tot = sum(cnt.values()); print('ע said like alef (Israeli):', {k: f'{v} ({100 * v / tot:.0f}%)' for k, v in cnt.items()})
tot = sum(het.values()); print('ח said like khaf (Israeli):', {k: f'{v} ({100 * v / tot:.0f}%)' for k, v in het.items()})
import numpy as np
print(f'words check on read speech, right words (>=2 consonants): n={len(skels)} median skel {np.median(skels):.2f}, below .2: {100 * np.mean(np.array(skels) < .2):.0f}%, below .4: {100 * np.mean(np.array(skels) < .4):.0f}%')
