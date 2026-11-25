"""The test bench's two text files, made from the repo's own Tehillim data (lyrics_tehillim.json: the lines the site
shows and the times it plays Rabbi Alouf at), so a new machine needs nothing but the repo:
  <lab>/out/tehillim-alouf/tehillim_alouf.json   Rabbi Alouf's pesukim as the site checks them — per perek the file and
       each pasuk's text, nikud, t0, t1 (the line's start and the next line's start, as the page's recLines does)
  <lab>/tehillim/tehillim_nikud.json             {perek: [pesukim with nikud]}, the text voice_register.py lines a
       reader up on
(The first bench — LAB_NOTES §39 — took Rabbi Alouf's times from a forced alignment that was lost with its machine; the
site itself uses these, so exams run on this index are the site's own check.)
usage: bench_index.py <lab dir>"""
import sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = sys.argv[1]
S = json.load(open(os.path.join(ROOT, 'lyrics_tehillim.json'), encoding='utf-8'))['s']
idx = {}; text = {}; n_ps = 0; n_timed = 0
for key, s in S.items():
    if not (key.startswith('t') and key[1:].isdigit()): continue
    n = int(key[1:]); f = s.get('b') or f'tehillim-{n:03d}.mp3'
    ev = [tuple(int(v) for v in x.split(',')) for x in ((s.get('t') or {}).get(f) or '').split(';') if x]
    t = {}
    for i, (ds, k) in enumerate(ev):
        if k < 0 or k in t: continue
        t[k] = (ds / 10, ev[i + 1][0] / 10 if i + 1 < len(ev) else ds / 10 + 8)
    have = os.path.exists(os.path.join(ROOT, 'static', 'tehillim', f))
    ps = [{'text': l, 'nikud': s['ln'][k], 't0': t[k][0] if (have and k in t) else None, 't1': t[k][1] if (have and k in t) else None} for k, l in enumerate(s['l'])]
    idx[str(n)] = {'file': f, 'pesukim': ps}; text[str(n)] = list(s['ln'])
    n_ps += len(ps); n_timed += sum(1 for p in ps if p['t0'] is not None)
os.makedirs(os.path.join(LAB, 'out', 'tehillim-alouf'), exist_ok=True); os.makedirs(os.path.join(LAB, 'tehillim'), exist_ok=True)
json.dump({'perakim': idx}, open(os.path.join(LAB, 'out', 'tehillim-alouf', 'tehillim_alouf.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(text, open(os.path.join(LAB, 'tehillim', 'tehillim_nikud.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print(f'{len(idx)} perakim, {n_ps} pesukim, {n_timed} with Rabbi Alouf\'s times')
