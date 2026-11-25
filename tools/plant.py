"""Planted mistakes for the exams: a pointed line (Tehillim) rewritten so that a reader who reads it right now "says"
another vowel than the page has — the checker must tell. Used by exam_voice.py (through the server) and by
bench/replay.py (offline, from an exam's kept vowel slots: the take's slots do not depend on the nikud, so one run of
the server per kind of recording serves every planted kind).
  OU: the page's o-vowels written u (holam, kamatz katan, hataf kamatz -> kubutz; holam male -> shuruk)
  IE: the page's hiriq written tsere                 EI: the page's e (tsere, segol, hataf segol) written hiriq
  EA: the page's e written patah (hataf segol -> hataf patah; not an e before a bare yod: that would make "ay")
  UO: the page's u written o (kubutz -> holam, shuruk -> holam male)
The Name is kept. planter(kind) -> plant(nikud line, one=None) -> (the new line, the changed words' indices, words);
one: a random.Random — one planted word per pasuk, chosen by it (a student rarely misreads more)."""
import os, sys
sys.path.insert(0, os.environ.get('DK_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nikud as NK
KINDS = ('OU', 'IE', 'EI', 'EA', 'UO')

def planter(PLANT):
    assert PLANT in KINDS, 'PLANT=OU, IE, EI, EA or UO'
    O_MARKS = {NK.HOLAM, NK.HOLAM_VAV, NK.QAMATS_QATAN, NK.HAT_QAM}
    def plant_word(w):
        if NK.NAME.search(w): return w
        groups = []
        for ch in w:
            if 'א' <= ch <= 'ת' or not groups: groups.append([ch, []])
            else: groups[-1][1].append(ch)
        out = []
        for c, ms in groups:
            if any(m in O_MARKS for m in ms):
                male = c == 'ו' and NK.DAGESH not in ms and not any(m in NK.VOWEL_MARKS and m not in O_MARKS for m in ms)
                ms = [(NK.DAGESH if male else NK.QUBUTS) if m in O_MARKS else m for m in ms]
            out.append(c + ''.join(ms))
        return ''.join(out)
    if PLANT == 'IE':   # the page's hiriq written tsere, the Name kept: the correct reader now "says i where the page says e"
        def plant_word(w): return w if NK.NAME.search(w) else w.replace(NK.HIRIQ, NK.TSERE)
    # the other way round, for the next kinds of false note (LAB_NOTES §39): EI = the page's e (tsere, segol, hataf segol)
    # written hiriq, so the correct reader "says e where the page says i"; EA = written patah (hataf segol -> hataf
    # patah; not an e before a bare yod, which would turn it into the diphthong ay); UO = the page's u written o (kubutz
    # -> holam, shuruk -> holam male). The Name kept.
    TARGET = {'EI': {NK.TSERE: NK.HIRIQ, NK.SEGOL: NK.HIRIQ, NK.HAT_SEG: NK.HIRIQ},
              'EA': {NK.TSERE: NK.PATAH, NK.SEGOL: NK.PATAH, NK.HAT_SEG: NK.HAT_PAT}, 'UO': {NK.QUBUTS: NK.HOLAM}}
    if PLANT in TARGET:
        def plant_word(w):
            if NK.NAME.search(w): return w
            groups = []
            for ch in w:
                if 'א' <= ch <= 'ת' or not groups: groups.append([ch, []])
                else: groups[-1][1].append(ch)
            out = []
            for j, (c, ms) in enumerate(groups):
                nxt = groups[j + 1] if j + 1 < len(groups) else None
                bare_yod = nxt is not None and nxt[0] == 'י' and not any(m in NK.VOWEL_MARKS or m == NK.DAGESH for m in nxt[1])
                if PLANT == 'UO' and c == 'ו' and NK.DAGESH in ms and not any(m in NK.VOWEL_MARKS for m in ms):
                    ms = [NK.HOLAM if m == NK.DAGESH else m for m in ms]   # shuruk -> holam male
                elif not (PLANT == 'EA' and bare_yod):
                    ms = [TARGET[PLANT].get(m, m) for m in ms]
                out.append(c + ''.join(ms))
            return ''.join(out)
    def plant(nik, one=None):
        words = nik.split(' '); news = [plant_word(w) for w in words]
        if one is not None:   # PLANT_ONE=1: one planted word per pasuk, chosen at random (a student rarely misreads more,
            # and a mistake made everywhere would also look like the reader's own way of speaking to a rule that weighs the take)
            cand = [j for j, (a, b) in enumerate(zip(words, news)) if a != b]
            pick = one.choice(cand) if cand else None
            news = [b if j == pick else a for j, (a, b) in enumerate(zip(words, news))]
        new = ' '.join(news)
        a, b = NK.parse_verse(nik), NK.parse_verse(new)
        assert len(a) == len(b)
        idx = [j for j, ((_, _, ua), (_, _, ub)) in enumerate(zip(a, b)) if [u['c'] for u in ua] != [u['c'] for u in ub]]
        return new, idx, len(a)
    return plant
