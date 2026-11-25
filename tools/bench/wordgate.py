"""Where may a vowel note be shown? Read from the note tables (bench/notes_table.py): every note the ear gives on an
exam's takes, shown today or not, on the reader's correct reading (false) and on the planted words (catches).

Today the notes are all-or-nothing per take (rule.vclean_of): a take under the gate shows none, also on words that were
heard well. Two things are tried here, alone and together:
  - a second opinion: the PHONE ear (the IPA recognizer, another network) also writes a vowel at the slot's time.
    'you' = it heard the vowel the note says the reader said; 'ref' = it heard the page's vowel; none / other.
    A note it contradicts could be dropped (fewer false notes); a note it confirms could be shown on a take the gate
    shuts (more catches).
  - a gate per word: the letter head's score on the word (hskel), the vowel head's own letter score (vskel).

usage: wordgate.py <exam name> [...]      DK_LAB_V: where the tables are.   RULES=name,... to list only some"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as RP
pct = RP.pct; KINDS = RP.ORDER

def load(exam): return json.load(open(os.path.join(RP.V, f'table_{exam}.json'), encoding='utf-8'))

def live(x): return x['shown']
def cand(x): return x['note'] and x['mark'] != 'off' and not x['cant']          # a note that could be shown at all
def open_(x): return x['vclean']                                                 # the take's gate (already without can't-hear)
def ph_you(c): return lambda x: x.get('pha') == 'you' and (x.get('phc') or 0) >= c
def ph_ref(c): return lambda x: x.get('pha') == 'ref' and (x.get('phc') or 0) >= c
def wscore(key, t): return lambda x: (x.get(key) or 0) >= t

RULES = collections.OrderedDict()
RULES['live'] = live
for c in (0, .3, .5, .7):
    RULES[f'drop-ref{c}'] = (lambda c: lambda x: live(x) and not ph_ref(c)(x))(c)                       # the phone ear contradicts: dropped
for c in (0, .3, .5):
    RULES[f'open-you{c}'] = (lambda c: lambda x: live(x) or (cand(x) and not open_(x) and ph_you(c)(x)))(c)   # it confirms: shown on a shut take
for a, b in ((0, 0), (.3, .3), (.5, .3), (.5, .5), (.3, 0)):
    RULES[f'both ref{a} you{b}'] = (lambda a, b: lambda x: (live(x) and not ph_ref(a)(x)) or (cand(x) and not open_(x) and ph_you(b)(x)))(a, b)
RULES['you-only0'] = lambda x: cand(x) and ph_you(0)(x)                                                   # a note only when the phone ear confirms, on any take
RULES['you-only.3'] = lambda x: cand(x) and ph_you(.3)(x)
RULES['not-ref0 any take'] = lambda x: cand(x) and not ph_ref(0)(x)                                       # no take gate at all; dropped only when contradicted
for key, t in (('hskel', .6), ('hskel', .7), ('vskel', .6), ('vskel', .7), ('vskel', .8)):
    RULES[f'word {key}>={t}'] = (lambda key, t: lambda x: live(x) or (cand(x) and not open_(x) and wscore(key, t)(x)))(key, t)
    RULES[f'word {key}>={t} + you0, ref.3'] = (lambda key, t: lambda x: (live(x) and not ph_ref(.3)(x)) or (cand(x) and not open_(x) and wscore(key, t)(x) and ph_you(0)(x)))(key, t)

def evaluate(T, rule):
    c = collections.Counter()
    for x in T:
        if x['kind'] == 'right':
            c['W'] += 1; c['false'] += bool(rule(x)); c['W_open'] += x['vclean']; c['false_open'] += bool(rule(x) and x['vclean'])
        elif x['planted']:
            hit = bool(x['note'] and rule(x)); c['P'] += 1; c['told'] += hit or x['mark'] == 'off'; c['P_' + x['kind']] += 1; c['told_' + x['kind']] += hit or x['mark'] == 'off'
            c['P_shut'] += not x['vclean']; c['told_shut'] += (hit or x['mark'] == 'off') and not x['vclean']
    return c

def opinion(T):
    """the phone ear's opinion on the notes: false ones (correct reading) and catches (planted, of the planted kind)"""
    for label, sel in (('false notes (correct reading)', lambda x: x['kind'] == 'right' and cand(x)), ('catches (planted word, the planted kind)', lambda x: x['planted'] and cand(x) and x.get('hit')),
                       ('other notes on a planted word', lambda x: x['planted'] and cand(x) and not x.get('hit'))):
        for gl, g in (('gate open', True), ('gate shut', False)):
            R = [x for x in T if sel(x) and x['vclean'] == g]; n = len(R)
            if not n: continue
            k = collections.Counter(x.get('pha') for x in R); strong = collections.Counter(x.get('pha') for x in R if (x.get('phc') or 0) >= .5)
            print(f'   {label:42s} {gl}: {n:4d} | the phone ear heard: ' + ', '.join(f'{a} {k[a]} ({100 * k[a] / n:.0f}%; sure {strong[a]})' for a in ('you', 'ref', 'other', 'none')))

if __name__ == '__main__':
    names = os.environ['RULES'].split(',') if os.environ.get('RULES') else list(RULES)
    for exam in sys.argv[1:]:
        T = load(exam); takes = {(x['per'], x['ps']): x['vclean'] for x in T}
        print(f'== {exam}: {len(takes)} takes, the gate open on {pct(sum(takes.values()), len(takes))}')
        opinion(T)
        print(f'   {"rule":34s} | false notes per right word        | planted told (all five kinds)     | on shut takes        | EI   EA   IE   OU   UO (%)')
        for nm in names:
            c = evaluate(T, RULES[nm]); per = ' '.join(f'{100 * c["told_" + k] / max(1, c["P_" + k]):4.0f}' for k in KINDS)
            print(f'   {nm:34s} | {pct(c["false"], c["W"]):33s} | {pct(c["told"], c["P"]):33s} | {c["told_shut"]:4d}/{c["P_shut"]:<4d} = {100 * c["told_shut"] / max(1, c["P_shut"]):4.1f}% | {per}')
