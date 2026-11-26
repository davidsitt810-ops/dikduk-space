"""The Name's two readings (nikud.read_name, v6.0), without models: it is read "Adonai" — and "Elohim" where it is
pointed so (a hiriq under its vav: אֲדֹנָי יֱהֹוִה). On the site's own Tehillim text: exactly the eight known pesukim
carry the second reading, each parses to the letters and vowels of "Elohim" (after its prefix, if any), and every other
Name in the 150 perakim still parses to "Adonai". (The server listens for the letters the parse gives: app.read_by_nikud.)"""
import os, sys, json, re
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); sys.path.insert(0, ROOT)
import nikud as NK
fails = []
def need(ok, *what):
    if not ok: fails.append(what)
    print('  ', 'ok ' if ok else 'BAD', *what)
S = json.load(open(os.path.join(ROOT, 'lyrics_tehillim.json'), encoding='utf-8'))['s']
KNOWN = {(68, 21), (69, 7), (71, 5), (71, 16), (73, 28), (109, 21), (140, 8), (141, 8)}
found = set(); adonai = bad_adonai = 0
for key, v in S.items():
    n = int(key[1:])
    for i, ln in enumerate(v.get('ln') or []):
        pv = NK.parse_verse(ln); plain = (v.get('l') or [None] * (i + 1))[i]
        for w, letters, units in pv:
            if not NK.NAME.search(w): continue
            vow = [u['c'] for u in units if u['kind'] == 'vowel']
            if NK.name_elohim(w):
                found.add((n, i + 1))
                need(letters.endswith('אלהימ') and vow[-3:] == ['E', 'O', 'I'], f'{n}:{i + 1} {w} is read Elohim', letters, vow)
            else:
                adonai += 1; bad_adonai += not (letters.endswith('דני') and vow[-2:] == ['O', 'A'])
need(found == KNOWN, 'the Name is pointed for "Elohim" in exactly the eight known pesukim of Tehillim', sorted(found ^ KNOWN))
need(adonai > 600 and bad_adonai == 0, f'every other Name ({adonai}) is read Adonai', bad_adonai)
for w, want in (('יֱהֹוִה', 'אלהימ'), ('וְלֵיהֹוִה', 'ולאלהימ'), ('יְהֹוָה', 'אדני'), ('לַיהֹוָה', 'לאדני'), ('בַּיהֹוָה', 'באדני')):
    need(NK.parse_word(w)[0] == want, w, '->', NK.parse_word(w)[0])
print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
