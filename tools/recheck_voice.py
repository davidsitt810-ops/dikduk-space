"""Re-check chosen pesukim of a new reader through /check (as exam_voice.py does) and print every word's mark.
usage: recheck.py <align dir> <audio> <perek:pasuk> [...]   (pasuk counted from 1)"""
import sys, os, json, subprocess
import requests
sys.path.insert(0, '/home/claude/dikduk-space'); import rule
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(HERE)
AL, SRC = sys.argv[1:3]
IDX = json.load(open(os.path.join(S, 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))['perakim']
for spec in sys.argv[3:]:
    n, i = (int(x) for x in spec.split(':')); i -= 1
    A = json.load(open(os.path.join(AL, f'{n}.json'), encoding='utf-8')); R = IDX[str(n)]; p = A['pesukim'][i]; q = R['pesukim'][i]
    path, off = (SRC.format(n=n), 0.0) if '{n' in SRC else (SRC, A['book_t0'])
    wav = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, off + p["t0"] - .25):.3f}', '-i', path, '-t', f'{p["t1"] - p["t0"] + .5:.3f}', '-ac', '1', '-ar', '16000', '-f', 'wav', '-'], capture_output=True).stdout
    alts = '|'.join(x['text'] for k, x in enumerate(R['pesukim']) if k != i and x.get('text'))
    out = requests.post('http://127.0.0.1:7861/check', params={'words': q['text'], 'nikud': q['nikud'], 'ref': R['file'], 't0': q['t0'], 't1': q['t1'], 'alts': alts},
                        data=wav, headers={'Content-Type': 'application/octet-stream'}, timeout=900).json()
    sm = rule.summarize(out)
    print(f'{n}:{i + 1}', ' '.join(f"{w}{'' if m == 'ok' else ('✕' if m == 'off' else '?')}" for w, m in zip(out['words'], sm['marks'])), '| why', [x for x in sm['why'] if x])
