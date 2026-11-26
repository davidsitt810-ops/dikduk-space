"""Exam jobs from a reader lined up outside Tehillim: LearnTefillah's haftarot (one reader, Brazil — a voice the
shipped heads never heard: the vowel head that learned him, nv6, was not shipped). The Mac batch of Nov 2 lined up and
kept 1,622 of his pesukim (dikduk_lab/out/man_lt_lthaf.jsonl: the file, the pasuk's times, its place in the text);
bench_lthaf_items.json holds those with their pointed text (made on the Mac, next to the manifest).
A second never-heard voice for the vowel notes: no hazzan (there is none for a haftarah), the pasuk's nikud as the
page, the haftarah's other pesukim as the rival lines.

usage: lt_jobs.py <bench_lthaf_items.json> <folder the recordings were copied under> <out jobs.json> [N=300] [max seconds=20] [seed=7]
       ELOHIM=only: the pesukim where the Name is read "Elohim", and no others (left out of the exams otherwise)"""
import sys, os, re, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import nikud as NK
SRC, ROOT, OUT = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 300; MAXS = float(sys.argv[5]) if len(sys.argv) > 5 else 20.0; SEED = int(sys.argv[6]) if len(sys.argv) > 6 else 7
D = json.load(open(SRC, encoding='utf-8'))
def clean(v):
    """the texts carry a little markup around the paseq (&thinsp;<small>׀</small>): out, the paseq with it"""
    v = re.sub(r'<[^>]+>', ' ', v); v = re.sub(r'&[a-zA-Z]+;', ' ', v).replace('׀', ' ')
    return NK.clean_verse(v)
MARKS = re.compile('[֑-ׇ]')
def words_of(nik): return [MARKS.sub('', w) for w, _, _ in NK.parse_verse(nik)]
chapters = sorted({(x['book'], x['ch']) for x in D['items']}); per_of = {bc: i + 1 for i, bc in enumerate(chapters)}
book_lines = {}   # a haftarah's pesukim (every chapter of its text), as the rival lines
for b, T in D['books'].items():
    book_lines[b] = [(ch, i + 1, ' '.join(words_of(clean(v)))) for ch, L in T.items() for i, v in enumerate(L) if v]
def elohim(nik):
    """the Name pointed for the reading "Elohim" (אֲדֹנָי יֱהֹוִה: a hiriq under the vav). The checker reads every Name
       "Adonai" — a fault of its own, noted in LAB_NOTES §43 — so on such a pasuk a correct reader differs from the page
       as parsed, and the word cannot be scored: left out"""
    for w in nik.split(' '):
        m = NK.NAME.search(w)
        if m and '\u05b4' in w[m.start():]: return True
    return False
jobs = []; skipped = {'no file': 0, 'long': 0, 'short': 0, 'the Name read Elohim': 0}
for x in D['items']:
    f = os.path.join(ROOT, x['rec'])
    if not os.path.exists(f): skipped['no file'] += 1; continue
    if x['t1'] - x['t0'] > MAXS: skipped['long'] += 1; continue
    nik = clean(x['nikud']); W = words_of(nik)
    if len(W) < 3: skipped['short'] += 1; continue
    if os.environ.get('ELOHIM') == 'only':   # only the pesukim with the Name read "Elohim" (to test that reading: app.read_by_nikud)
        if not elohim(nik): continue
    elif elohim(nik): skipped['the Name read Elohim'] += 1; continue
    alts = '|'.join(t for ch, ln, t in book_lines[x['book']] if not (ch == x['ch'] and ln == x['line']) and t)
    jobs.append({'id': x['id'], 'per': per_of[(x['book'], x['ch'])], 'ps': x['line'], 'file': f, 't0': x['t0'], 't1': x['t1'], 'words': ' '.join(W), 'nikud': nik, 'alts': alts, 'skel': x['skel']})
random.seed(SEED); random.shuffle(jobs); jobs = jobs[:N]
json.dump({'reader': 'lthaf', 'items': jobs}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'{len(jobs)} pesukim of {len({j["file"] for j in jobs})} haftarot -> {OUT}; left out: {skipped}; words {sum(len(j["words"].split()) for j in jobs)}, seconds {sum(j["t1"] - j["t0"] for j in jobs):.0f}')
