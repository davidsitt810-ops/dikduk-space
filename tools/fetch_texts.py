"""Sefaria's "Miqra according to the Masorah" (the same pointed text the checker uses for Tehillim) for other books:
<out>/<Book>_nikud.json = {chapter: [verse, ...]}. usage: fetch_texts.py <out dir> Book:chapters [...]"""
import sys, os, json, time, requests
OUT = sys.argv[1]; S = requests.Session(); S.headers.update({'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)'})
for spec in sys.argv[2:]:
    book, n = spec.split(':'); out = {}
    for c in range(1, int(n) + 1):
        r = S.get(f'https://www.sefaria.org/api/texts/{book.replace(" ", "_")}.{c}', params={'vhe': 'Miqra_according_to_the_Masorah', 'context': 0, 'commentary': 0}, timeout=60); time.sleep(0.3)
        d = r.json(); assert d.get('heVersionTitle') == 'Miqra according to the Masorah', (book, c, d.get('heVersionTitle'))
        out[str(c)] = d['he']
    json.dump(out, open(os.path.join(OUT, f'{book.replace(" ", "_")}_nikud.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(book, len(out), 'chapters', sum(len(v) for v in out.values()), 'verses', flush=True)
