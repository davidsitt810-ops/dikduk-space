"""LearnTefillah -> the Mac's batch 2: which file is which text, as perek_to_manifest.py jobs.
Readers (tools/LAB_NOTES §36, speaker check spk_check.py):
  lthaf   the haftarot (one reader, Brazil — "Especiais"): 77 haftarot, a NEW voice
  slevy   Hacham Sion Levy, Esther (one recording, three encodings: the 320 kbps one), a NEW voice
  tawil   Rabbi Max Tawil (= Miqra's Tawil, already in training): Ruth, Eikha, Esther, Kohelet, Mishlei 1-5, Iyov 1-20
  benhaim Hacham Baruch Ben Haim (already in training, his Tehillim): Shir HaShirim (= the archive's, .89) and Esther
  zami    Abe Zami, the Torah by aliyot (already in training from the archive: 9 other parashiyot, aliyot trimmed)
left out: the Tehillim (Ben Haim's, the exams' voice), the holiday Torah readings (Hazzan Faraj Samra — the checker's
never-heard test voice), the ta'amim lessons.
writes <out>/texts/*.json, <out>/jobs_<voice>.txt (relpath:perek:text=texts/x.json:book=tag per line), <out>/book_jobs.txt,
<out>/haftarot.tsv. usage: lt_build.py <texts dir> <haftarot_calendar.json> <LT files list> <out dir>"""
import sys, os, json, re, collections, requests
TX, CAL, LIST, OUT = sys.argv[1:5]
os.makedirs(os.path.join(OUT, 'texts'), exist_ok=True)
files = [l.rstrip('\n') for l in open(LIST, encoding='utf-8') if l.strip()]
BOOKS = {}
def book(name):
    fn = name.replace(' ', '_')
    if fn not in BOOKS: BOOKS[fn] = json.load(open(os.path.join(TX, f'{fn}_nikud.json'), encoding='utf-8'))
    return BOOKS[fn]
def verses_of(bk, c): return list(book(bk)[str(c)])

def parse_ref(ref):
    """'Isaiah 40:27-41:16, 42:1-3' / 'Hosea 14:2-10; Micah 7:18-20' -> [(book, [(c0, v0, c1, v1), ...]), ...]"""
    out = []; cur = None
    for part in re.split(r'[;,]\s*', ref.strip()):
        m = re.match(r'^((?:I{1,2} )?[A-Za-z]+(?: [A-Za-z]+)?) (\d.*)$', part.strip())
        if m: cur = m.group(1); span = m.group(2); out.append((cur, []))
        else: span = part.strip()
        a, _, b = span.partition('-')
        c0, _, v0 = a.partition(':'); c0 = int(c0); v0 = int(v0) if v0 else 1
        if not b: c1, v1 = c0, v0
        elif ':' in b: c1, v1 = (int(x) for x in b.split(':'))
        else: c1, v1 = c0, int(b)
        out[-1][1].append((c0, v0, c1, v1))
    return out

def text_of(bk, spans, trim0=0, trim1=0):
    """{chapter: verses} with only the spans' verses (others ''); trim: drop that many verses at the start / end"""
    keep = []
    for c0, v0, c1, v1 in spans:
        for c in range(c0, c1 + 1):
            n = len(verses_of(bk, c))
            for v in range(v0 if c == c0 else 1, (min(v1, n) if c == c1 else n) + 1): keep.append((c, v))
    keep = keep[trim0:len(keep) - trim1 if trim1 else None]
    out = {}
    for c, v in keep:
        if str(c) not in out: out[str(c)] = [''] * len(verses_of(bk, c))
        out[str(c)][v - 1] = verses_of(bk, c)[v - 1]
    return out, len(keep)

slug = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
jobs = collections.defaultdict(list); haf_rows = []
def add_text(name, t):
    p = f'texts/{name}.json'; json.dump(t, open(os.path.join(OUT, p), 'w', encoding='utf-8'), ensure_ascii=False); return p

# ---- the parashiyot in order (Sefaria's Torah index: names and aliyot)
S = requests.Session(); S.headers.update({'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)'})
TORAH = ['Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy']; PAR = []
for bk in TORAH:
    for nd in S.get(f'https://www.sefaria.org/api/v2/raw/index/{bk}', timeout=60).json()['alt_structs']['Parasha']['nodes']:
        PAR.append({'name': nd['sharedTitle'], 'book': bk, 'whole': nd['wholeRef'], 'aliyot': nd['refs'][:7], 'bi': TORAH.index(bk)})
by_book = collections.defaultdict(list)
for p in PAR: by_book[p['bi']].append(p)
def par_of(book_dir_no, n):   # LT folder '1x-Parasha <Book>' (x = 1..5) / '0x <Book>' + 'nn <Parasha>' -> the parasha
    return by_book[book_dir_no - 1][n - 1]

# ---- haftarot
cal = json.load(open(CAL, encoding='utf-8'))
def top(custom, name):
    v = cal[custom].get(name) or []
    v = [(r.replace(' | ', '; '), k) for r, k in v if r]
    return v[0][0] if v else None
# the 54 parashiyot in order: Sefaria's calendar (custom=sephardi, five years of Shabbatot: haftarot_calendar.json) where
# the parasha's own haftarah showed; the others (a special Shabbat or a joined parasha every year) the Sephardic
# custom's. Each entry: passages that do not overlap — the reader read one of them; the wrong one finds nothing.
HAF = [['Isaiah 42:5-21'], ['Isaiah 54:1-10'], ['Isaiah 40:27-41:16'], ['II Kings 4:1-23'], ['I Kings 1:1-31'], ['Malachi 1:1-2:7'],
       ['Hosea 11:7-12:12', 'Hosea 12:13-14:10'], ['Obadiah 1:1-21', 'Hosea 12:13-14:10'], ['Amos 2:6-3:8'], ['I Kings 3:15-4:1'], ['Ezekiel 37:15-28'], ['I Kings 2:1-12'],
       ['Jeremiah 1:1-2:3', 'Isaiah 27:6-28:13'], ['Ezekiel 28:25-29:21'], ['Jeremiah 46:13-28'], ['Judges 5:1-31'], ['Isaiah 6:1-13'], ['Jeremiah 34:8-22, 33:25-26'],
       ['I Kings 5:26-6:13'], ['Ezekiel 43:10-27'], ['I Kings 18:20-39'], ['I Kings 7:13-26', 'I Kings 7:40-50'], ['I Kings 7:40-50', 'I Kings 7:51-8:21'],
       ['Isaiah 43:21-44:23'], ['Jeremiah 7:21-28, 9:22-23'], ['II Samuel 6:1-19'], ['II Kings 4:42-5:19'], ['II Kings 7:3-20'], ['Ezekiel 22:1-16'],
       ['Ezekiel 20:2-20', 'Amos 9:7-15'], ['Ezekiel 44:15-31'], ['Jeremiah 32:6-27'], ['Jeremiah 16:19-17:14'],
       ['Hosea 2:1-22'], ['Judges 13:2-25'], ['Zechariah 2:14-4:7'], ['Joshua 2:1-24'], ['I Samuel 11:14-12:22'], ['Judges 11:1-33'], ['Micah 5:6-6:8'],
       ['I Kings 18:46-19:21', 'Jeremiah 1:1-2:3'], ['Jeremiah 1:1-2:3', 'Jeremiah 2:4-28'], ['Jeremiah 2:4-28', 'Jeremiah 1:1-2:3'],
       ['Isaiah 1:1-27'], ['Isaiah 40:1-26'], ['Isaiah 49:14-51:3'], ['Isaiah 54:11-55:5'], ['Isaiah 51:12-52:12'], ['Isaiah 54:1-10'], ['Isaiah 60:1-22'],
       ['Isaiah 61:10-63:9'], ['Hosea 14:2-10; Micah 7:18-20; Joel 2:15-27', 'Isaiah 55:6-56:8'], ['II Samuel 22:1-51', 'Hosea 14:2-10; Micah 7:18-20; Joel 2:15-27'],
       ['Joshua 1:1-9']]
SPECIAL = {1: ['I Samuel 20:18-42'], 2: ['Isaiah 66:1-24'], 3: ['II Kings 12:1-17'], 4: ['I Samuel 15:2-34'], 5: ['Ezekiel 36:16-36'],
           6: ['Ezekiel 45:18-46:15'], 7: ['Malachi 3:4-24'], 8: ['Joshua 5:2-6:1'], 9: ['II Kings 23:1-9, 23:21-25'], 10: ['Ezekiel 37:1-14'],
           11: ['II Samuel 22:1-51'], 12: ['Isaiah 10:32-12:6'], 13: ['Ezekiel 1:1-28, 3:12'], 14: ['Habakkuk 3:1-19'], 15: ['Zechariah 14:1-21'],
           16: ['I Kings 8:2-21'], 17: ['Ezekiel 38:18-39:16'], 18: ['I Kings 8:54-66'], 19: ['Joshua 1:1-9'], 20: ['I Samuel 1:1-2:10'],
           21: ['Jeremiah 31:1-19'], 23: ['Jonah 1:1-4:11'], 24: ['Zechariah 2:14-4:7'], 25: ['I Kings 7:40-50']}
def overlaps(a, b):
    pa = parse_ref(a); pb = parse_ref(b)
    sa = {(bk, c, v) for bk, sp in pa for c0, v0, c1, v1 in sp for c in range(c0, c1 + 1) for v in range(1, 200) if (c, v) >= (c0, v0) and (c, v) <= (c1, v1)}
    sb = {(bk, c, v) for bk, sp in pb for c0, v0, c1, v1 in sp for c in range(c0, c1 + 1) for v in range(1, 200) if (c, v) >= (c0, v0) and (c, v) <= (c1, v1)}
    return bool(sa & sb)
for f in files:
    m = re.match(r'^17-Haftara/0(\d) [^/]+/(\d\d) ([^/]+)/[^/]+\.mp3$', f)
    if not m: continue
    grp, n, label = int(m.group(1)), int(m.group(2)), m.group(3).strip()
    if grp <= 5:
        p = par_of(grp, n); name = p['name']; tag = 'haf' + slug(name)
        cands = HAF[PAR.index(p)]   # the Sephardic haftarah first; a second, different passage where customs or years differ
    else:
        name = f'special {n} {label}'; tag = f'hafsp{n:02d}'; cands = SPECIAL.get(n, [])
    for ci, ref in enumerate(cands):
        for bi, (bk, spans) in enumerate(parse_ref(ref)):
            t, nv = text_of(bk, spans); bt = f'{tag}{"abc"[ci]}{bi or ""}_'
            tp = add_text(bt.rstrip('_'), t)
            for c in sorted(int(k) for k in t):
                if any(t[str(c)]): jobs['lthaf'].append(f'{f}:{c}:text={tp}:book={bt}')
            haf_rows.append((f, name, ref, bk, nv, bt))

# ---- Rabbi Tawil's books, one perek per file
def per_file(voice, pat, bk, tag, fix=None):
    for f in files:
        m = re.match(pat, f)
        if not m: continue
        n = int(m.group(1)); ns = fix(f, n) if fix else [n]
        for k in ns:
            if str(k) in book(bk): jobs[voice].append(f'{f}:{k}:text=texts/{bk}_nikud.json:book={tag}')
per_file('tawil', r'^06-Meguilat Ruth/(\d+)/-/[^/]+\.mp3$', 'Ruth', 'ruth')
per_file('tawil', r'^07-Eikha/(\d+)/-/[^/]+\.mp3$', 'Lamentations', 'eikha')
per_file('tawil', r'^09-Meguilat Esther/Meguilat Esther (\d+)/-/[^/]+\.mp3$', 'Esther', 'esther')
per_file('tawil', r'^08-Kohelet/\d+-Perek (\d+)/-/Kohelet-Perek \1--\.mp3$', 'Ecclesiastes', 'kohelet')
per_file('tawil', r'^27-Mishlei/(\d+)/-/[^/]+\.mp3$', 'Proverbs', 'mishle', fix=lambda f, n: [3, 4] if n in (3, 4) else [n])   # folder 3 holds "Daleth", 4 "Ghimel"
per_file('tawil', r'^28-Iyov/(\d+)/-/[^/]+\.mp3$', 'Job', 'iyob')
per_file('benhaim', r'^05-Shir Hashirim/\d+-Perek (\d+)/-/[^/]+\.mp3$', 'Song_of_Songs', 'shir')
for bk in ('Ruth', 'Lamentations', 'Esther', 'Ecclesiastes', 'Proverbs', 'Job', 'Song_of_Songs'):
    add_text(f'{bk}_nikud', book(bk))

# ---- Abe Zami's Torah, by aliyot, nine parashiyot the archive did not have
ZAMI = {"Chayei Sara", 'Vayishlach', 'Shemot', 'Beshalach', 'Kedoshim', "Beha'alotcha", 'Balak', 'Devarim', 'Ki Tavo'}
AL = {'rishon': 1, 'sheni': 2, 'shelishi': 3, 'revii': 4, 'chamishi': 5, 'shishi': 6, 'shevii': 7, 'shevi': 7}
for f in files:
    m = re.match(r'^11 - Parasha \(Full\)/1(\d)-Parasha [^/]+/(\d\d) [^/]+/(?:\d - )?([A-Za-z]+)/[^/]+\.mp3$', f)   # the aliyah from its folder
    if not m or int(m.group(1)) > 5: continue   # 16-Parasha Special: Hazzan Faraj Samra, the never-heard test voice
    p = par_of(int(m.group(1)), int(m.group(2)))
    if p['name'] not in ZAMI: continue
    i = AL.get(m.group(3).lower())
    if not i: continue
    (bk, spans), = parse_ref(p['aliyot'][i - 1])
    t, nv = text_of(bk, spans, trim0=1 if i > 1 else 0, trim1=1 if i < 7 else 0)   # Sephardic aliyot may move a verse
    bt = f't{slug(p["name"])}{i}_'; tp = add_text(bt.rstrip('_'), t)
    for c in sorted(int(k) for k in t):
        if any(t[str(c)]): jobs['zami'].append(f'{f}:{c}:text={tp}:book={bt}')

for v, js in jobs.items():
    open(os.path.join(OUT, f'jobs_{v}.txt'), 'w', encoding='utf-8').write('\n'.join(js) + '\n')
    print(f'{v}: {len(js)} jobs, {len({j.split(":")[0] for j in js})} files')
open(os.path.join(OUT, 'book_jobs.txt'), 'w', encoding='utf-8').write(
    "slevy\testher\tEsther_nikud.json\t1-10\t09-Meguilat Esther/Chacham Sion Levy - Meguilat Esther(2).mp3\n"
    "benhaim\testher\tEsther_nikud.json\t1-10\t09-Meguilat Esther/Megillat Esther- Ben Haim.mp3\n")
with open(os.path.join(OUT, 'haftarot.tsv'), 'w', encoding='utf-8') as fo:
    for r in haf_rows: fo.write('\t'.join(str(x) for x in r) + '\n')
print('haftarot:', len({r[0] for r in haf_rows}), 'files,', len(haf_rows), 'candidate texts')
missing = [f for f in files if f.startswith('17-Haftara/0') and f not in {r[0] for r in haf_rows}]
print('haftarot without a text:', missing)
