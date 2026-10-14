"""Pointed Hebrew (nikud + te'amim, Sefaria's "Miqra according to the Masorah") -> what a Sephardic reader says.
For every word: the letters (final forms folded, the Name read as אדני) and a list of pronunciation UNITS, each a
consonant or a vowel with the IPA sounds it may be, so a forced aligner can place it and report which sound was
actually made (the dagesh decides b/v, k/x, p/f, t/(th); the shin/sin dot decides ʃ/s; ע and ח are offered their
throat and plain sounds; vowels are offered the sounds of their class).

Vowel classes (Sephardic): patah, kamatz gadol, hataf patah -> A; kamatz katan, hataf kamatz, holam -> O... (see VOWEL).
A sheva is left out of the units (silent or a short murmur; the aligner's blanks absorb it). A furtive patah under a
final ח / ע / הּ is said before the consonant (רוּחַ = ru-ah).
"""
import re, unicodedata

# marks
DAGESH = 'ּ'; SHIN = 'ׁ'; SIN = 'ׂ'; RAFE = 'ֿ'; METEG = 'ֽ'; CGJ = '͏'
SHEVA = 'ְ'; HAT_SEG = 'ֱ'; HAT_PAT = 'ֲ'; HAT_QAM = 'ֳ'; HIRIQ = 'ִ'; TSERE = 'ֵ'; SEGOL = 'ֶ'
PATAH = 'ַ'; QAMATS = 'ָ'; HOLAM = 'ֹ'; HOLAM_VAV = 'ֺ'; QUBUTS = 'ֻ'; QAMATS_QATAN = 'ׇ'
VOWEL_MARKS = {SHEVA, HAT_SEG, HAT_PAT, HAT_QAM, HIRIQ, TSERE, SEGOL, PATAH, QAMATS, HOLAM, HOLAM_VAV, QUBUTS, QAMATS_QATAN}
ACCENT = re.compile('[֑-ֽֿׅ֯ׄ͏]')   # te'amim, meteg, rafe, dots, CGJ: not sounds
FIN = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}

# vowel mark -> class
VOWEL = {PATAH: 'A', QAMATS: 'A', HAT_PAT: 'A', QAMATS_QATAN: 'O', HAT_QAM: 'O', HOLAM: 'O', HOLAM_VAV: 'O',
         SEGOL: 'E', TSERE: 'E', HAT_SEG: 'E', HIRIQ: 'I', QUBUTS: 'U', SHEVA: 'SHEVA'}
# vowel class -> IPA alternatives (as in the espeak-phone model's alphabet)
VOWEL_IPA = {'A': ['a', 'ɑ', 'aː', 'ɐ', 'æ', 'ɑː'], 'E': ['e', 'ɛ', 'eː', 'ɛː', 'e̞'], 'I': ['i', 'ɪ', 'iː', 'ɨ'],
             'O': ['o', 'ɔ', 'oː', 'ɔː', 'o̞', 'oʊ'], 'U': ['u', 'ʊ', 'uː'], 'SHEVA': ['ə', 'ɛ', 'e', 'ɨ']}
# consonant -> IPA alternatives; (with dagesh, without dagesh) where the dagesh matters
CONS = {'ב': (['b'], ['v']), 'ג': (['ɡ'], ['ɡ', 'ɣ']), 'ד': (['d'], ['d', 'ð']), 'ה': (['h'], ['h']), 'ו': (['v', 'w'], ['v', 'w']),
        'ז': (['z'], ['z']), 'ח': (['ħ', 'h', 'x', 'χ'], ['ħ', 'h', 'x', 'χ']), 'ט': (['t'], ['t']), 'י': (['j'], ['j']),
        'כ': (['k'], ['x', 'χ', 'k']), 'ל': (['l'], ['l']), 'מ': (['m'], ['m']), 'נ': (['n'], ['n']), 'ס': (['s'], ['s']),
        'ע': (['ʕ', 'ʔ', 'h'], ['ʕ', 'ʔ', 'h']), 'פ': (['p'], ['f']), 'צ': (['ts', 's'], ['ts', 's']), 'ק': (['k', 'q'], ['k', 'q']),
        'ר': (['r', 'ɾ', 'ʁ'], ['r', 'ɾ', 'ʁ']), 'ש': (['ʃ'], ['ʃ']), 'ת': (['t'], ['t', 'θ'])}
NAME = re.compile('י[^א-ת]*ה[^א-ת]*ו[^א-ת]*ה(?![א-ת])')

def clean_verse(v):
    """drop paragraph marks, sof pasuq, the ketiv in (…) — the qere in […] is what is read"""
    v = re.sub(r'\{[^}]*\}', ' ', v)
    v = re.sub(r'\([^)]*\)', ' ', v)
    v = v.replace('[', ' ').replace(']', ' ').replace('׃', ' ').replace('׆', ' ').replace('־', ' ')
    return re.sub(r'\s+', ' ', v).strip()

def read_name(w):
    """the Name is read אדני: at the start of a word with its own hataf, after a prefix without it"""
    m = NAME.search(w)
    if not m: return w
    before = w[:m.start()]
    repl = 'אֲדֹנָי' if not re.search('[א-ת]', before) else 'אדֹנָי'
    return before + repl + w[m.end():]

def parse_word(w):
    """-> letters (folded, pointed marks stripped) and units [{'c': letter or class, 'kind': 'cons'|'vowel', 'alts': [...], 'k': letter index}]"""
    w = read_name(ACCENT.sub('', w))
    # split into (letter, marks)
    groups = []
    for ch in w:
        if 'א' <= ch <= 'ת': groups.append([ch, ''])
        elif groups and unicodedata.category(ch).startswith('M'): groups[-1][1] += ch
    letters = ''.join(FIN.get(g[0], g[0]) for g in groups)
    units = []
    n = len(groups)
    for k, (c0, marks) in enumerate(groups):
        c = FIN.get(c0, c0); dag = DAGESH in marks; shin = SHIN in marks; sin = SIN in marks
        vmark = next((m for m in marks if m in VOWEL_MARKS), None)
        last = k == n - 1
        prev_v = groups[k - 1][1] if k else ''
        # matres lectionis
        if c == 'ו' and dag and vmark is None:                      # shuruk
            units.append({'c': 'U', 'kind': 'vowel', 'alts': VOWEL_IPA['U'], 'k': k}); continue
        if c == 'ו' and vmark in (HOLAM, HOLAM_VAV) and not dag:      # holam male
            units.append({'c': 'O', 'kind': 'vowel', 'alts': VOWEL_IPA['O'], 'k': k}); continue
        if c == 'י' and vmark is None and not dag:
            pv = next((m for m in prev_v if m in VOWEL_MARKS), None)
            if pv in (HIRIQ, TSERE, SEGOL): continue                 # the vowel was said on the letter before
            if pv in (PATAH, QAMATS, HOLAM, QUBUTS, QAMATS_QATAN, HAT_PAT) or (k and DAGESH in prev_v and groups[k-1][0] == 'ו'):
                units.append({'c': 'י', 'kind': 'cons', 'alts': ['j', 'i'], 'k': k}); continue   # the glide of a diphthong
            # otherwise a consonantal yod without its own vowel (rare): keep it
        if c == 'א' and vmark is None: continue                      # a silent alef
        if c == 'ה' and last and not dag:                            # final he without mappiq: silent
            if vmark: units.append({'c': VOWEL.get(vmark), 'kind': 'vowel', 'alts': VOWEL_IPA.get(VOWEL.get(vmark), []), 'k': k}) if VOWEL.get(vmark) not in (None, 'SHEVA') else None
            continue
        # furtive patah: said before a final ח / ע / הּ
        furtive = last and vmark == PATAH and (c in ('ח', 'ע') or (c == 'ה' and dag)) and k > 0
        if furtive:
            units.append({'c': 'A', 'kind': 'vowel', 'alts': VOWEL_IPA['A'], 'k': k})
        # the consonant
        if c == 'ש':
            alts = ['s'] if sin else ['ʃ']
        elif c == 'א':
            alts = []                                                 # a glottal catch at most: listed (for the vowel head) but never aligned
        elif c in CONS:
            alts = CONS[c][0] if (dag or c in ('ח', 'ע', 'י', 'ו', 'ה', 'ז', 'ט', 'ל', 'מ', 'נ', 'ס', 'צ', 'ק', 'ר')) else CONS[c][1]
            if c in ('ב', 'כ', 'פ', 'ת', 'ג', 'ד'): alts = CONS[c][0] if dag else CONS[c][1]
        else:
            alts = None
        if alts is not None: units.append({'c': c, 'kind': 'cons', 'alts': alts, 'k': k, 'dagesh': dag})
        # its vowel
        if not furtive and vmark and VOWEL.get(vmark) not in (None, 'SHEVA'):
            units.append({'c': VOWEL[vmark], 'kind': 'vowel', 'alts': VOWEL_IPA[VOWEL[vmark]], 'k': k})
    return letters, units

def parse_verse(v):
    return [(w, *parse_word(w)) for w in clean_verse(v).split(' ') if re.search('[א-ת]', w)]

if __name__ == '__main__':
    import json, sys
    T = json.load(open(sys.argv[1], encoding='utf-8'))
    for ref in ['1:1', '23:1', '2:6', '5:9', '150:6']:
        ch, vs = ref.split(':'); v = T[ch][int(vs) - 1]
        print(ref, clean_verse(v))
        for w, letters, units in parse_verse(v):
            print('   ', letters.ljust(8), ' '.join(('%s' % (u['alts'][0] if u['kind'] == 'cons' else u['c'].lower())) for u in units))
