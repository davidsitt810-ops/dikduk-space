"""Concrete reproducers for the server-side (Python) findings, run against rule.py and the functions exec'd out of app.py."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); SPACE = os.path.join(HERE, '..', '..')
src = open(os.path.join(SPACE, 'app.py'), encoding='utf-8').read()
def pyfn(name, stop):
    i = src.index(f'def {name}('); j = src.index(stop, i); return src[i:j]
# the rule from rule.py; the Hebrew word helpers and score_take cut out of app.py (it loads the models on import)
import sys; sys.path.insert(0, SPACE); import rule
code = ('import numpy as np, re\n' + src[src.index("NIK = re.compile"):src.index('\ndef he_read')] + '\n' + pyfn('he_words', '\ndef skeleton') + pyfn('score_take', "\n@app.get('/score')"))
ns = dict(vars(rule)); exec(code, ns)
hm, summarize, score_take, marks_of, clean_of = ns['head_median'], ns['summarize'], ns['score_take'], ns['marks_of'], ns['clean_of']

print('== 1. head_median on short lines (n>=2 words only count)')
for hs in ([0.1], [0.1, 0.9], [0.1, 0.1, 0.9], [0.1, 0.1, 0.1, 0.9], [0.1, 0.1, 0.1, 0.1, 0.9], [0.9, 0.1, 0.1]):
    TW = [{'n': 2, 'hskel': h} for h in hs]
    print('   hskel', hs, '-> head_median', hm(TW), '-> clean', clean_of(TW))

print('== 2. score_take with a repeated word in the line (dict(zip(W, marks)) collapses duplicates)')
W = 'קדוש קדוש קדוש'
for marks in (['off', 'ok', 'ok'], ['ok', 'ok', 'off']):
    S = {'marks': marks, 'why': [None] * 3, 'throat': [], 'vowels': [], 'miss': {}, 'clean': True, 'hazzan': True}
    J = {'summary': S, 'do': 'right', 'labels': {}, 'words': W, 'check': True, 'graded': True}
    r = score_take(J); print('   marks', marks, '-> tally', r['tally'], '| claims:', r['claims'])

print('== 3. summarize: F shorter than TW (fit_against would have to return fewer entries than words)')
out = {'words': ['א', 'ב'], 'take': {'words': [{'n': 2, 'skel': .9, 'hskel': .9}, {'n': 2, 'skel': .9, 'hskel': .9}], 'phones': ['a'] * 10, 'dur': 3}, 'fit': [{'fit': .9}]}
try: print('   ', summarize(out)['marks'])
except Exception as e: print('   raises', type(e).__name__, e)
print('== 3b. summarize: fit = [] (what fit_against returns when the hazzan words had no ids)')
out['fit'] = []; s = summarize(out); print('   marks', s['marks'], 'hazzan flag', s['hazzan'], '(page: F=[] is truthy -> !F false -> says "as the hazzan sings it")')

print('== 4. summarize: zero words / take without phones+dur / vowels keyed by strings / throat entries')
for name, out in (
    ('zero words', {'words': [], 'take': {'words': [], 'phones': [], 'dur': 1.0}}),
    ('no phones, no dur', {'words': ['אב'], 'take': {'words': [{'n': 1, 'skel': .5}]}}),
    ('vowels keyed by str', {'words': ['אבג', 'דהו'], 'take': {'words': [{'n': 2, 'skel': .9, 'hskel': .9}, {'n': 2, 'skel': .9, 'hskel': .9}], 'phones': ['a'] * 9, 'dur': 2}, 'vowels': {'1': [{'k': 1, 'you': 'A', 'ref': 'E', 'm': .9}]}, 'vowel_names': {'A': 'ah (patah)', 'E': 'eh (segol)'}}),
    ('vowels index out of range', {'words': ['אבג'], 'take': {'words': [{'n': 2, 'skel': .9, 'hskel': .9}], 'phones': ['a'] * 9, 'dur': 2}, 'vowels': {'3': [{'k': 1, 'you': 'A', 'ref': 'E'}]}}),
    ('vowel entry with you=None', {'words': ['אבג'], 'take': {'words': [{'n': 2, 'skel': .9, 'hskel': .9}], 'phones': ['a'] * 9, 'dur': 2}, 'vowels': {0: [{'k': 1, 'you': None, 'ref': 'E'}]}}),
    ('throat entry without k', {'words': ['עב'], 'take': {'words': [{'n': 1, 'skel': .5, 'throat': [{'c': 'ע', 'v': 'plain'}]}], 'phones': ['a'] * 9, 'dur': 2}}),
    ('W shorter than TW', {'words': ['אב'], 'take': {'words': [{'n': 1, 'skel': .5, 'throat': [{'c': 'ע', 'k': 0, 'v': 'plain'}]}, {'n': 1, 'skel': .5, 'throat': [{'c': 'ע', 'k': 0, 'v': 'plain'}]}], 'phones': ['a'] * 9, 'dur': 2}}),
    ('ref words shorter than take', {'words': ['עב', 'עג'], 'take': {'words': [{'n': 1, 'skel': .5, 'throat': [{'c': 'ע', 'k': 0, 'v': 'plain'}]}, {'n': 1, 'skel': .5, 'throat': [{'c': 'ע', 'k': 0, 'v': 'plain'}]}], 'phones': ['a'] * 9, 'dur': 2}, 'ref': {'words': [{'throat': [{'k': 0, 'v': 'throat'}]}]}}),
):
    try: s = summarize(out); print('   ok  ', name, '->', {k: s[k] for k in ('marks', 'no_speech', 'cant_hear', 'vowels', 'throat')})
    except Exception as e: print('   RAISES', name, '->', type(e).__name__, e)

print('== 5. score_take with older-shaped summaries')
for name, S in (('oldest stored shape', {'clean': True, 'dur': 2, 'hazzan': True, 'marks': ['ok'], 'miss': {}, 'throat': [{'c': 'ע', 'k': 0, 'v': 'plain', 'w': 'עב'}], 'vowels': []}),
                ('vowel entry without against', {'clean': True, 'hazzan': True, 'marks': ['ok'], 'throat': [], 'vowels': [{'w': 'עב', 'k': 1, 'you': 'ah', 'ref': 'eh'}]}),
                ('summary without throat key', {'clean': True, 'hazzan': True, 'marks': ['ok'], 'vowels': []})):
    J = {'summary': S, 'do': 'right', 'labels': {}, 'words': 'עב', 'check': True, 'graded': True}
    try: print('   ok  ', name, score_take(J)['tally'])
    except Exception as e: print('   RAISES', name, '->', type(e).__name__, e)

print('== 6. two adjacent skipped words (drops tie within the margin): dropped=False so the skip-vs-swap guard is off')
TW = [{'n': 3, 'skel': .05, 'kept': .2, 'hskel': .9, 'drop': 30.0, 'swap': 9.0}, {'n': 3, 'skel': .05, 'kept': .2, 'hskel': .9, 'drop': 28.0, 'swap': 1.0}, {'n': 3, 'skel': .9, 'kept': 1, 'hskel': .9, 'drop': -3.0, 'swap': None}, {'n': 3, 'skel': .9, 'kept': 1, 'hskel': .9, 'drop': -3.0}]
print('   ', marks_of(TW, None, 0.1, clean_of(TW)))
print('== 7. a swap whose argmax pair is suppressed as "same" hides a second, independent swap pair')
TW = [{'n': 3, 'skel': .05, 'kept': .2, 'hskel': .9, 'drop': 40.0, 'swap': 9.0}, {'n': 3, 'skel': .9, 'kept': 1, 'hskel': .9, 'drop': 1.0, 'swap': 1.0}, {'n': 3, 'skel': .5, 'kept': .8, 'hskel': .9, 'drop': 2.0, 'swap': 8.5}, {'n': 3, 'skel': .5, 'kept': .8, 'hskel': .9, 'drop': 2.0}]
print('   ', marks_of(TW, None, 0.1, clean_of(TW)))
