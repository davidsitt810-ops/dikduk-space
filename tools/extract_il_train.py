"""Israeli read speech (FLEURS he_il TRAIN split, CC BY 4.0) as OTHER-VOICES training data for the Hebrew-letter head.
Israelis say ע like א and ח like כ, so the targets are written that way (ע -> א, ח -> כ): the head learns their
voices without learning that an alef sound is an ayin. Clips whose transcript has digits or Latin letters are left
out (the audio says them, the Hebrew letters do not). Streams the tar (no wav on disk); writes feat/<id>.npz and
manifest rows with src "il2" through extract_eg.py's own save(). usage: extract_il_train.py [max_clips=1500]"""
import sys, os, io, csv, json, re, time, tarfile, glob
HERE = os.path.dirname(os.path.abspath(__file__))
MAXN = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
src = open(os.path.join(HERE, 'extract_eg.py'), encoding='utf-8').read().split('\ndone = set()')[0]
ns = {'__file__': os.path.join(HERE, 'extract_eg.py'), '__name__': 'extract_eg_lib'}; sys.argv = [sys.argv[0]]; exec(src, ns)
save, he_words, decode_audio, MAN = ns['save'], ns['he_words'], ns['decode_audio'], ns['MAN']
root = glob.glob(os.path.join(HERE, '..', 'fleurs_train', 'hfcache', 'datasets--google--fleurs', 'snapshots', '*', 'data', 'he_il'))[0]
meta = {}
for row in csv.reader(open(os.path.join(root, 'train.tsv'), encoding='utf-8'), delimiter='\t'):
    if len(row) < 4: continue
    meta[row[1]] = (row[2], row[3])
done = set()
if os.path.exists(MAN):
    for l in open(MAN, encoding='utf-8'):
        try: done.add(json.loads(l)['id'])
        except Exception: pass
BAD = re.compile(r'[0-9A-Za-z]')
MAP = str.maketrans({'ע': 'א', 'ח': 'כ'})
n = 0; skipped = 0; t0 = time.time()
with tarfile.open(os.path.join(root, 'audio', 'train.tar.gz'), 'r|gz') as tf:
    for m in tf:
        if not m.isfile() or not m.name.endswith('.wav'): continue
        f = os.path.basename(m.name); cid = 'il2_' + f[:-4]
        if cid in done or f not in meta: continue
        raw, norm = meta[f]
        if BAD.search(norm): skipped += 1; continue
        words = [w.translate(MAP) for w in he_words(norm)]
        if len(words) < 4: skipped += 1; continue
        data = tf.extractfile(m).read()
        try:
            x = decode_audio(data)
            if x.shape[0] < 16000 * 2 or x.shape[0] > 16000 * 20: skipped += 1; continue
            save(cid, x, words, {'src': 'il2', 'pid': 'il2', 'rec': f, 'line': 0, 'orig': ' '.join(he_words(norm))}); n += 1
        except Exception as e:
            print('skip', f, str(e)[:80], flush=True); continue
        if n % 50 == 0: print(f'israeli train {n} (skipped {skipped}) {int(time.time() - t0)} s', flush=True)
        if n >= MAXN: break
print('done', n, 'skipped', skipped, f'{int(time.time() - t0)} s', flush=True)
