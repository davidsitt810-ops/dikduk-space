"""v6.0, no models needed: the second opinion and the trust of a vowel note (vowels.py), and the rule that shows it
(rule.note_shown, rule.rate_notes) — on small made-up takes whose answers are worked out by hand, and on David's own
three notes of Nov 1 with the numbers the server gave them (the facts copied from its answers; no audio here).
Guards the pieces the exams' numbers rest on: which of the phone ear's vowels belongs to a slot, what its opinion is
called, the weights, the two bars, and that a server without weights changes nothing."""
import os, sys, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import vowels as VW, rule
fails = []
def need(ok, *what):
    if not ok: fails.append(what)
    print('  ', 'ok ' if ok else 'BAD', *what)
P = lambda p, t, c=.9: {'p': p, 't': t, 'c': c}

print('which of the phone ear\'s vowels belongs to a slot (vowels.phone_vowel_at):')
ph = [P('l', 4.35), P('ɑ', 4.43, .71), P('a', 6.31, .86), P('x', 6.49), P('s', 6.65), P('a', 6.75, .52), P('r', 6.97)]
need(VW.phone_vowel_at(ph, 6.40) == ('A', .86, .09), 'a long vowel: its mark 90 ms before the slot, no consonant between -> that vowel', VW.phone_vowel_at(ph, 6.40))
need(VW.phone_vowel_at(ph, 6.55) == ('', None, None), 'a slot between two consonants with no vowel of its own -> none (not the vowel across the consonant)', VW.phone_vowel_at(ph, 6.55))
need(VW.phone_vowel_at(ph, 6.74)[0] == 'A' and VW.phone_vowel_at(ph, 6.74)[2] == .01, 'the same moment', VW.phone_vowel_at(ph, 6.74))
need(VW.phone_vowel_at(ph, 4.44) == ('AO', .71, .01), 'ɑ may be an "a" or an "o"', VW.phone_vowel_at(ph, 4.44))
need(VW.phone_vowel_at([P('m', 1.0), P('ə', 1.05), P('e', 1.12, .6), P('n', 1.3)], 1.02) == ('E', .6, .1), 'a murmur does not stand in the way', VW.phone_vowel_at([P('m', 1.0), P('ə', 1.05), P('e', 1.12, .6), P('n', 1.3)], 1.02))
need(VW.phone_vowel_at([P('e', 1.0, .6)], 1.3) == ('', None, None), 'farther than a quarter of a second -> none')
need(VW.phone_vowel_at([], 1.0) == ('', None, None) and VW.phone_vowel_at(None, 1.0) == ('', None, None), 'no phones at all -> none')
need(VW.phone_vowel_at([P('aɪ', 1.0, .8)], 1.0)[0] == 'AI', 'a diphthong is both of its vowels')

print('what the opinion is called (vowels.opinion_of):')
for d, want in (({'you': 'E', 'ref': 'I', 'ph': 'E'}, 'you'), ({'you': 'E', 'ref': 'I', 'ph': 'I'}, 'ref'), ({'you': 'E', 'ref': 'I', 'ph': 'AI'}, 'ref'), ({'you': 'O', 'ref': 'U', 'ph': 'AO'}, 'you'),
                ({'you': 'A', 'ref': 'O', 'ph': 'AO'}, 'other'), ({'you': 'E', 'ref': 'I', 'ph': 'O'}, 'other'), ({'you': 'E', 'ref': 'I', 'ph': ''}, 'none'), ({'you': 'E', 'ref': 'I'}, 'none')):
    need(VW.opinion_of(d) == want, d, '->', VW.opinion_of(d), '(wanted', want + ')')

print('David\'s own notes of Nov 1, the facts as the server gave them (vowels.note_trust, rule.note_shown):')
# (note, the word's letter-head and vowel-head scores, the take's gate, what must show)
ahsar = ({'you': 'A', 'ref': 'E', 'm': 1.0, 'ph': 'A', 'phc': .864, 'phd': .09}, {'hskel': .867, 'vskel': .97}, True)
al = ({'you': 'E', 'ref': 'A', 'm': 1.0, 'ph': 'E', 'phc': .842, 'phd': .02}, {'hskel': .459, 'vskel': .412}, False)
menohot = ({'you': 'O', 'ref': 'U', 'm': .99, 'ph': 'AO', 'phc': .239, 'phd': .0}, {'hskel': .737, 'vskel': .677}, False)
for name, (d, w, gate), want in (('"ahsar" (a clear take, the phone ear\'s vowel in the same syllable only)', ahsar, .5312), ('the "eh" of his "al" (a take under the gate, both ears)', al, .7753), ('"menohot" (under the gate, both ears)', menohot, .7406)):
    p = VW.note_trust(d, w, gate, None, None); shown = rule.note_shown(dict(d, p=p), gate)
    need(abs(p - want) < .002 and shown, name, 'trust', p, '(the server:', str(want) + ')', 'shown' if shown else 'held back')
need(VW.note_trust({'you': 'E', 'ref': 'I', 'm': 1.0, 'ph': ''}, {'hskel': 1.0, 'vskel': 1.0}, False, None, None) < rule.RULE['vpu'], 'under the gate a perfect word and slot with no second opinion stays under the bar: both ears must agree')
need(VW.note_trust({'you': 'E', 'ref': 'I', 'm': 1.0, 'ph': ''}, {'hskel': 1.0, 'vskel': 1.0}, True, None, None) >= rule.RULE['vp'], '... and over the gate it shows')
need(VW.note_trust({'you': 'E', 'ref': 'I', 'm': 1.0, 'ph': 'I', 'phc': .8, 'phd': .01}, {'hskel': .9, 'vskel': .9}, True, None, None) < rule.RULE['vp'], 'a clear take, the phone ear sure of the page\'s vowel at the same moment: held back')
need(len(VW.TRUST_W) == len(VW.TRUST_NAMES) == len(VW.note_features(ahsar[0], ahsar[1], True, .8, .05)), 'one weight per fact')

print('the rule (rule.note_shown) and a server without weights:')
need(rule.note_shown({'you': 'E', 'ref': 'I'}, True) and not rule.note_shown({'you': 'E', 'ref': 'I'}, False), 'no trust on the note (a server before v6.0): the take\'s gate, as before')
need(rule.note_shown({'you': 'E', 'ref': 'I', 'p': .01}, True, nikud=False) and not rule.note_shown({'you': 'E', 'ref': 'I', 'p': .99}, False, nikud=False), 'a line without nikud: the take\'s gate, whatever the trust')
need(rule.note_shown({'p': rule.RULE['vp']}, True) and not rule.note_shown({'p': rule.RULE['vp'] - .0001}, True) and rule.note_shown({'p': rule.RULE['vpu']}, False) and not rule.note_shown({'p': rule.RULE['vpu'] - .0001}, False), 'the two bars, each on its side of the gate')

print('the server\'s last step on a take (rule.rate_notes) and what the page then shows (rule.summarize):')
W = lambda w, h, v, vow: {'w': w, 'n': 3, 'skel': .9, 'hskel': h, 'vskel': v, 'kept': 1.0, 'pw': .1, 'drop': -20.0, 'swap': -20.0, 't0': 0, 't1': 1, 'throat': [], 'vow': vow}
slot = lambda k, heard, t: {'k': k, 'heard': heard, 'mass': {x: (1.0 if x == heard else 0.0) for x in 'AEIOU'}, 'p': 1.0, 't0': t, 't1': t + .02}
def answer(h):
    """three words, two notes: on word 0 with the phone ear agreeing at the same moment, on word 2 with the phone ear hearing the page's vowel"""
    return {'words': ['אבג', 'דהו', 'זחט'], 'vowels_nikud': {'0': [{'k': 0, 'you': 'E', 'ref': 'I', 'm': 1.0}], '2': [{'k': 1, 'you': 'O', 'ref': 'U', 'm': 1.0}]},
            'take': {'dur': 3.0, 'snr': 40.0, 'gap': .05, 'rival': None, 'phones': [P('b', .4), P('e', .5, .9), P('ɡ', .7), P('d', 1.2), P('a', 1.3), P('z', 2.2), P('u', 2.31, .9), P('t', 2.6)] + [P('m', 2.7 + i / 100) for i in range(6)],
                     'words': [W('אבג', h, h, [slot(0, 'E', .5)]), W('דהו', h, h, []), W('זחט', h, h, [slot(1, 'O', 2.3)])]}}
for h, gate in ((.9, True), (.5, False)):
    out = rule.rate_notes(answer(h)); sm = rule.summarize(out); a, b = out['vowels_nikud']['0'][0], out['vowels_nikud']['2'][0]
    need(a['ph'] == 'E' and b['ph'] == 'U' and VW.opinion_of(a) == 'you' and VW.opinion_of(b) == 'ref' and out.get('vowels_2nd') and out.get('vowels_trust'), f'heads at {h}: the two opinions on the notes', a.get('ph'), b.get('ph'))
    need(sm['clean'] == gate and [v['i'] for v in sm['vowels']] == [0] and b['p'] < rule.RULE['vp'], f'heads at {h} (the gate {"open" if gate else "shut"}): the confirmed note shows, the contradicted one does not', a['p'], b['p'], [v['i'] for v in sm['vowels']])
    need(sm['vpart'] == (not gate) and not sm['vlost'], f'heads at {h}: "only partly checked" exactly under the gate', sm['vpart'], sm['vlost'])
keep = VW.TRUST_W; VW.TRUST_W = None
try:
    for h, gate in ((.9, True), (.5, False)):
        out = rule.rate_notes(answer(h)); sm = rule.summarize(out)
        need('p' not in out['vowels_nikud']['0'][0] and not out.get('vowels_trust') and len(sm['vowels']) == (2 if gate else 0) and sm['vlost'] == (not gate) and not sm['vpart'],
             f'no weights, heads at {h}: no trust given, the take\'s gate alone — as v5.9 — and "not checked" under it', len(sm['vowels']), sm['vlost'])
finally: VW.TRUST_W = keep
out = answer(.5); del out['vowels_nikud']; out['vowels'] = {'0': [{'k': 0, 'you': 'E', 'ref': 'I', 'm': 1.0}]}; sm = rule.summarize(rule.rate_notes(out))
need('p' not in out['vowels']['0'][0] and 'ph' in out['vowels']['0'][0] and not sm['vowels'] and sm['vlost'] and not sm['vpart'], 'a line without nikud (a hazzan alone): the opinion is given, no trust; under the gate nothing shows and the page says "not checked"')
print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
