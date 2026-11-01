"""shva.py without the models (stdlib only at the top, so CI can run it): shva_marks on a table of pointed words whose
reading a Sephardic teacher gives the same way every time, and every branch of notes() — which shva a note may rest on
(the trusted rules, the hazzan's clear reading) and which it may not. app.py imports shva at startup, so this also
catches a shva.py that does not import. Exit code 1 on any failure (CI runs this on every push)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import shva
fails = []
# word -> [(letter, kind, rule)] for every sheva in it
MARKS = {'יִשְׁמְרוּ': [('ש', 'nah', 'first'), ('מ', 'na', 'second')], 'יְנַהֲלֵנִי': [('י', 'na', 'start')], 'יַרְבִּיצֵנִי': [('ר', 'nah', 'short')],
         'מְנֻחוֹת': [('מ', 'na', 'start')], 'נַפְשִׁי': [('פ', 'nah', 'short')], 'בְּרֵאשִׁית': [('ב', 'na', 'start')], 'הַלְלוּ': [('ל', 'na', 'twin')],
         'הַמְּלָכִים': [('מ', 'na', 'dagesh')], 'שׁוֹמְרִים': [('מ', 'na', 'long')], 'מַלְכּוֹ': [('ל', 'nah', 'short')], 'אַתְּ': [('ת', 'nah', 'final')],
         'לֵךְ': [('כ', 'nah', 'final')], 'שָֽׁמְרָה': [('מ', 'na', 'meteg')], 'לַיְלָה': [('י', 'nah', 'diphthong')],
         'וּבְדֶרֶךְ': [('ב', 'nah', 'shuruk'), ('כ', 'nah', 'final')], 'שָׁלוֹם': []}
for w, want in MARKS.items():
    got = [(m['c'], m['kind'], m['rule']) for m in shva.shva_marks(w)]
    if got != want: fails.append(('shva_marks', w, got, 'want', want))
if [m['k'] for m in shva.shva_marks('יִשְׁמְרוּ')] != [1, 2]: fails.append(('letter index k', shva.shva_marks('יִשְׁמְרוּ')))
# the trusted rules are rules shva_marks gives (a renamed rule would silently lose its notes)
if not shva.TRUSTED <= set(shva.NA_RULES) | set(shva.NAH_RULES): fails.append(('TRUSTED names an unknown rule', shva.TRUSTED))
# notes(): s(...) is one probed shva slot as probe() gives it
def s(k, kind, rule, heard, c='מ'): return {'k': k, 'c': c, 'kind': kind, 'rule': rule, 'heard': heard}
NA, NAH, LONG = ('na', 'start'), ('nah', 'short'), ('na', 'long')
CASES = [   # (what, student, ref, trusted, want)
    ('trusted na said, no hazzan: nothing', {0: [s(0, *NA, 'vowel')]}, None, None, {}),
    ('trusted na swallowed, no hazzan: a note by the rule', {0: [s(0, *NA, 'none')]}, None, None, {'0': [('vowel', 'none', 'rule')]}),
    ('trusted nah given a vowel, no hazzan', {'1': [s(1, *NAH, 'vowel')]}, None, None, {'1': [('none', 'vowel', 'rule')]}),
    ('trusted na swallowed, the hazzan says it: by the hazzan', {0: [s(0, *NA, 'none')]}, {0: [s(0, *NA, 'vowel')]}, None, {'0': [('vowel', 'none', 'hazzan')]}),
    ('string keys on the hazzan side match int keys', {0: [s(0, *NA, 'none')]}, {'0': [s(0, *NA, 'vowel')]}, None, {'0': [('vowel', 'none', 'hazzan')]}),
    ('trusted na, the hazzan clearly does not say it: no note (one ear is wrong)', {0: [s(0, *NA, 'none')]}, {0: [s(0, *NA, 'none')]}, None, {}),
    ('trusted na, the hazzan unsure: by the rule', {0: [s(0, *NA, 'none')]}, {0: [s(0, *NA, 'unsure')]}, None, {'0': [('vowel', 'none', 'rule')]}),
    ('the student unsure: never a note', {0: [s(0, *NA, 'unsure')]}, {0: [s(0, *NA, 'vowel')]}, None, {}),
    ('untrusted rule, no hazzan: nothing', {0: [s(2, *LONG, 'none')]}, None, None, {}),
    ('untrusted rule, the hazzan unsure: nothing', {0: [s(2, *LONG, 'none')]}, {0: [s(2, *LONG, 'unsure')]}, None, {}),
    ('untrusted rule, the hazzan clearly silent and the student says it: the hazzan decides', {0: [s(2, *LONG, 'vowel')]}, {0: [s(2, *LONG, 'none')]}, None, {'0': [('none', 'vowel', 'hazzan')]}),
    ('untrusted rule, student and hazzan agree: nothing', {0: [s(2, *LONG, 'vowel')]}, {0: [s(2, *LONG, 'vowel')]}, None, {}),
    ('the hazzan for another letter of the word does not count', {0: [s(0, *NA, 'none')]}, {0: [s(3, *NA, 'none')]}, None, {'0': [('vowel', 'none', 'rule')]}),
    ('a caller trusting nothing: only the hazzan decides', {0: [s(0, *NA, 'none')]}, None, set(), {}),
    ('a caller trusting long', {0: [s(2, *LONG, 'none')]}, None, {'long'}, {'0': [('vowel', 'none', 'rule')]}),
    ('no student slots', {}, {0: [s(0, *NA, 'vowel')]}, None, {}), ('no student at all', None, None, None, {}),
]
for what, st, ref, tr, want in CASES:
    out = shva.notes(st, ref, tr); got = {i: [(d['want'], d['you'], d['by']) for d in ds] for i, ds in out.items()}
    if got != want: fails.append(('notes: ' + what, got, 'want', want))
    for ds in out.values():
        if any(set(d) != {'k', 'c', 'kind', 'rule', 'you', 'want', 'by'} for d in ds): fails.append(('notes: the fields of a note', what, ds))
print(f'shva rules: {len(MARKS)} words, {len(CASES)} note cases')
print('FAILS:' if fails else 'ALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
