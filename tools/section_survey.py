"""Survey pizmonim.com's reading sections (David has the community's permission to train on the archive): for each
section page, the rows (number, title) and their recordings (id, label), saved as <out>/index_<section>.json, and a
summary of the readers per section. Fetched politely with the checker's own user agent.
usage: section_survey.py <out dir> <section> [<section> ...]   (section = a section.php?maqam= value, or a full path)"""
import sys, os, re, json, time, html, collections
import requests
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)', 'Accept': '*/*'}
BASE = 'https://pizmonim.com'
S = requests.Session(); S.headers.update(UA)
def rows_of(page):
    out = []
    for tr in re.findall(r'<tr>(.*?)</tr>', page, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
        recs = [(int(a), html.unescape(re.sub('<[^>]+>', '', b)).strip()) for a, b in re.findall(r"book\.php\?recording=(\d+)'?\"?>(.*?)</a>", tr, re.S)]
        if not tds or not recs: continue
        txt = [html.unescape(re.sub('<[^>]+>', '', t)).strip() for t in tds]
        out.append({'num': txt[0], 'title': txt[2] if len(txt) > 2 else '', 'recs': recs})
    return out
for sec in sys.argv[2:]:
    path = sec if sec.endswith('.php') or '?' in sec else f'section.php?maqam={sec}'
    r = S.get(f'{BASE}/{path}', timeout=60); time.sleep(0.6)
    name = re.sub(r'[^A-Za-z0-9]+', '_', sec).strip('_')
    open(os.path.join(OUT, f'page_{name}.html'), 'w', encoding='utf-8').write(r.text)
    rows = rows_of(r.text)
    json.dump(rows, open(os.path.join(OUT, f'index_{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    readers = collections.Counter(lab for row in rows for _, lab in row['recs'])
    print(f'== {sec} [{r.status_code}, {len(r.text)} bytes]: {len(rows)} rows, {sum(len(x["recs"]) for x in rows)} recordings')
    print('   ' + '; '.join(f'{k} ({v})' for k, v in readers.most_common(14)))
    if rows: print('   e.g.', rows[0]['num'], rows[0]['title'][:40], '|', rows[-1]['num'], rows[-1]['title'][:40])
