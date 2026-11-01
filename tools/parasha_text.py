"""The text of one Torah reading for the aligner and the cutter (voice_register.py / perek_to_manifest.py, TEXT=...):
{chapter: [verses]} from a book fetched by fetch_texts.py, cut to the parasha. The verses before it in its first chapter
are kept as empty strings, so pasuk numbers stay right (items <voice>_<parasha><chapter>_<pasuk>); the verses after it
in its last chapter are dropped. voice_register.py skips a stretch whose verses are all empty.
usage: parasha_text.py <texts dir> <tag>=<Book>:<chapter>:<verse>-<chapter>:<verse> [...]
   e.g. parasha_text.py texts noah=Genesis:6:9-11:32 nitzavim=Deuteronomy:29:9-31:30"""
import sys, os, json
D = sys.argv[1]
for spec in sys.argv[2:]:
    tag, _, rng = spec.partition('='); book, _, span = rng.partition(':'); a, _, b = span.partition('-')
    (c0, v0), (c1, v1) = (tuple(int(x) for x in a.split(':')), tuple(int(x) for x in b.split(':')))
    B = json.load(open(os.path.join(D, f'{book}_nikud.json'), encoding='utf-8')); out = {}
    for c in range(c0, c1 + 1):
        vs = list(B[str(c)])
        if c == c1: vs = vs[:v1]
        if c == c0: vs = [''] * (v0 - 1) + vs[v0 - 1:]
        out[str(c)] = vs
    json.dump(out, open(os.path.join(D, f'parasha_{tag}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{tag}: {book} {c0}:{v0}-{c1}:{v1}, {sum(1 for vs in out.values() for v in vs if v)} verses')
