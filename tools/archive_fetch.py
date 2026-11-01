"""pizmonim.com's Miqra reading sections (Torah, haftarot, megillot, Mishle, Iyob) — the Syrian community's archive,
which David has the community's permission to train on. Phase 'resolve': every recording's mp3 (from its book.php page,
or the page's own download links) and its size (HEAD) -> <out>/catalog.json. Phase 'fetch': the mp3s, one at a time,
politely, with the checker's own user agent, into <out>/mp3/<section>/. Resumes from what is on disk.
usage: archive_fetch.py resolve|fetch <out dir> [max MB]"""
import sys, os, re, json, time, html, urllib.parse
import requests
PHASE, OUT = sys.argv[1], sys.argv[2]; MAXMB = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
UA = {'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)', 'Accept': '*/*'}
BASE = 'https://pizmonim.com'
SECTIONS = ['Pentateuch', 'Haftarot', 'Song_of_Songs', 'Ruth', 'Esther', 'Lamentations', 'Ecclesiastes', 'Mishle', 'Iyob']
S = requests.Session(); S.headers.update(UA)
CAT = os.path.join(OUT, 'catalog.json')
cat = json.load(open(CAT, encoding='utf-8')) if os.path.exists(CAT) else {}
def save(): json.dump(cat, open(CAT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
def direct_links(page):
    """rows of a section page that offers its mp3s directly: [(num, title, mp3 path, reader)]"""
    out = []
    for tr in re.findall(r'<tr>(.*?)</tr>', page, re.S):
        tds = [html.unescape(re.sub('<[^>]+>', ' ', t)).strip() for t in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        for path, who in re.findall(r"href='(MP3/[^']+?\.mp3)'.*?</span>\s*([^<]*)<br", tr, re.S):
            out.append((tds[0] if tds else '', tds[2] if len(tds) > 2 else '', '/' + path, html.unescape(who).strip()))
    return out
if PHASE == 'resolve':
    for sec in SECTIONS:
        rows = json.load(open(os.path.join(OUT, f'index_{sec}.json'), encoding='utf-8'))
        for row in rows:
            for rid, label in row['recs']:
                k = f'r{rid}'
                if k in cat and cat[k].get('mp3'): continue
                r = S.get(f'{BASE}/book.php?recording={rid}', timeout=60); time.sleep(0.5)
                m = re.search(r"mp3:\s*'([^']+\.mp3)'", r.text, re.I)
                cat[k] = {'id': rid, 'section': sec, 'num': row['num'], 'title': row['title'], 'label': label, 'mp3': m.group(1) if m else None, 'status': r.status_code}
                save()
        page = open(os.path.join(OUT, f'page_{sec}.html'), encoding='utf-8').read()
        for num, title, path, who in direct_links(page):
            k = 'd' + path
            if k not in cat: cat[k] = {'id': None, 'section': sec, 'num': num, 'title': title, 'label': who, 'mp3': path, 'status': 200}
        save()
    for k, e in cat.items():
        if e.get('mp3') and not e.get('bytes'):
            r = S.head(BASE + urllib.parse.quote(e['mp3']), timeout=60, allow_redirects=True); time.sleep(0.3)
            e['bytes'] = int(r.headers.get('Content-Length') or 0); e['head'] = r.status_code
    save()
    from collections import defaultdict
    by = defaultdict(lambda: [0, 0])
    for e in cat.values():
        if e.get('mp3'): by[e['section']][0] += 1; by[e['section']][1] += e.get('bytes') or 0
    for s, (n, b) in by.items(): print(f'{s:15s} {n:4d} recordings {b / 1e6:8.0f} MB')
    print(f"total {sum(n for n, _ in by.values())} recordings, {sum(b for _, b in by.values()) / 1e6:.0f} MB; no mp3: {sum(1 for e in cat.values() if not e.get('mp3'))}")
else:
    total = 0; n = 0; t0 = time.time()
    for k, e in sorted(cat.items(), key=lambda kv: (SECTIONS.index(kv[1]['section']), kv[0])):
        if not e.get('mp3') or e.get('skip'): continue   # skip: one voice's 50 more parashiyot (more voices, not more hours)
        d = os.path.join(OUT, 'mp3', e['section']); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, (f"{e['id']}_" if e['id'] else '') + os.path.basename(e['mp3']))
        if os.path.exists(dst) and os.path.getsize(dst) > 10000: total += os.path.getsize(dst); e['file'] = dst; continue
        if total / 1e6 > MAXMB: print('stopping at the size limit'); break
        r = S.get(BASE + urllib.parse.quote(e['mp3']), timeout=600); time.sleep(0.5); n += 1
        if r.status_code == 200 and len(r.content) > 10000:
            open(dst + '.part', 'wb').write(r.content); os.replace(dst + '.part', dst); total += len(r.content); e['file'] = dst
        else: e['err'] = r.status_code
        save()
        if n % 10 == 0: print(f'{n} fetched, {total / 1e6:.0f} MB on disk [{int(time.time() - t0)} s]', flush=True)
    save(); print(f'done: {sum(1 for e in cat.values() if e.get("file"))} files, {total / 1e6:.0f} MB [{int(time.time() - t0)} s]')
