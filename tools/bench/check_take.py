"""One recording through a server as the lab page checks a pasuk of Tehillim — Rabbi Alouf's line as the hazzan, the
perek's other lines as rivals (pid), the nikud — and what the page would show (rule.summarize).
usage: check_take.py <perek> <pasuk> <audio file> [--noref] [--words]     DK_URL: the server (default the local one)
       TRUST=<weights json> VP=<bar>: rate the notes here with weights being tried (bench/trust.py)
       --words: each word's letter-head score, vowel slots and marks"""
import sys, os, json, requests
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import rule
BASE = os.environ.get('DK_URL', 'http://127.0.0.1:7861')
n, ps, path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; flags = set(sys.argv[4:])
s = json.load(open(os.path.join(ROOT, 'lyrics_tehillim.json'), encoding='utf-8'))['s'][f't{n}']; f = s.get('b') or f'tehillim-{n:03d}.mp3'
ev = [tuple(int(v) for v in x.split(',')) for x in ((s.get('t') or {}).get(f) or '').split(';') if x]
t = {k: (ds / 10, ev[i + 1][0] / 10 if i + 1 < len(ev) else ds / 10 + 8) for i, (ds, k) in enumerate(ev) if k >= 0}
k = ps - 1; prm = {'words': s['l'][k], 'nikud': s['ln'][k], 'pid': f't{n}'}
if '--noref' not in flags and k in t: prm.update({'ref': f, 't0': t[k][0], 't1': t[k][1]})
r = requests.post(BASE + '/check', params=prm, data=open(path, 'rb').read(), headers={'Content-Type': 'application/octet-stream'}, timeout=900)
out = r.json()
if r.status_code != 200: sys.exit(f'server said {r.status_code}: {out}')
if os.environ.get('TRUST'):   # weights to try (a json from bench/trust.py), on an answer from a server that does not rate its notes yet
    import vowels as VW
    VW.TRUST_W = json.load(open(os.environ['TRUST']))['w']; rule.rate_notes(out)
if os.environ.get('VP'): rule.RULE['vp'] = float(os.environ['VP'])
sm = rule.summarize(out); TW = out['take']['words']
print(f"{os.path.basename(path)}  ({n}:{ps})  server {out.get('version', '?')}")
print(f"  clean {sm['clean']}, vowels checked {sm.get('vclean')}, head median {rule.head_median(TW)}, gap {sm['gap']}, noise estimate {sm.get('snr')} dB, noisy line {sm.get('noisy')}, vowels-not-checked line {sm.get('vlost')}, "
      f"line wrong {sm['line_wrong']}, can't hear {sm['cant_hear']}, no speech {sm['no_speech']}")
print('  words: ' + '  '.join(f"{w}{ {'ok': '✓', 'unsure': '?', 'off': '✕'}.get(m, '·') }" for w, m in zip(out['words'], sm['marks'])))
for v in sm['vowels']: print(f"  vowel: {v['w']}: you {v['you']} where the {v['against']} has {v['ref']}")
for key in ('vowels', 'vowels_nikud'):   # every note the ear gave, shown or held back, with its second opinion and trust
    for i, ds in (out.get(key) or {}).items():
        for d in ds:
            if 'ph' in d or 'p' in d: print(f"     ({key}: {out['words'][int(i)]} you {d['you']} ref {d['ref']} m {d.get('m')} | phone ear {d.get('ph')!r} {d.get('phc')} | trust {d.get('p')} -> {'shown' if rule.note_shown(d, sm['vclean'], out.get('vowels_nikud') is not None) and sm['marks'][int(i)] != 'off' else 'held back'})")
for x in sm['throat']: print(f"  throat: {x['c']} in {x['w']}: {x['v']} (hazzan {x.get('hazzan')})")
for x in sm['shva']: print('  shva:', x)
if '--words' in flags:
    for i, w in enumerate(TW):
        vow = ' '.join(f"{v['heard']}@{v['k']}({max(v['mass'].values()) / max(1e-6, sum(v['mass'].values())):.2f})" for v in (w.get('vow') or []))
        print(f"    {out['words'][i]:12s} n {w.get('n')} skel {w.get('skel')} hskel {w.get('hskel')} vskel {w.get('vskel')} kept {w.get('kept')} pw {w.get('pw')} | {vow}")
    print('  raw hazzan notes:', json.dumps(out.get('vowels'), ensure_ascii=False)); print('  raw nikud notes:', json.dumps(out.get('vowels_nikud'), ensure_ascii=False))
