"""Throat letters and vowels, reader against reader, on the same perakim: what the phone ear and the Arabic ear heard.
usage: compare_register.py <perakim like 1,2,23> <name>=<align dir> ..."""
import sys, os, json, collections
P = [int(x) for x in sys.argv[1].split(',')]
for spec in sys.argv[2:]:
    name, d = spec.split('=', 1)
    ph = {c: collections.Counter() for c in 'עחאהכ'}; ar = {c: collections.Counter() for c in 'עחאכ'}; vow = collections.defaultdict(collections.Counter); n_ok = 0; ps = []
    for n in P:
        f = os.path.join(d, f'{n}.json')
        if not os.path.exists(f): continue
        A = json.load(open(f, encoding='utf-8')); n_ok += 1; ps.append(A['quality']['mean_p'])
        for u in A['units']:
            if u.get('heard') is None: continue
            if u['kind'] == 'cons' and u['c'] in ph: ph[u['c']][u['heard']] += 1
            elif u['kind'] != 'cons': vow[u['c']][u['heard']] += 1
        for a in A['ar_letters']:
            if a.get('heard') and a['c'] in ar: ar[a['c']][a['heard']] += 1
    print(f'== {name}: {n_ok} perakim, mean p {sum(ps) / max(1, len(ps)):.3f}')
    for c in 'עח':
        t = sum(ph[c].values()); ta = sum(ar[c].values())
        print(f'  {c} phone ear (n={t}):', ', '.join(f'{k} {100 * v / t:.0f}%' for k, v in ph[c].most_common(4)), '|  arabic ear (n=%d):' % ta, ', '.join(f'{k} {100 * v / ta:.0f}%' for k, v in ar[c].most_common(4)))
    for c in 'אכ':
        ta = sum(ar[c].values())
        if ta: print(f'  {c} arabic ear (n={ta}):', ', '.join(f'{k} {100 * v / ta:.0f}%' for k, v in ar[c].most_common(3)))
    print('  vowels:', ' | '.join(f'{c}: ' + ', '.join(f'{k} {100 * v / sum(vow[c].values()):.0f}%' for k, v in vow[c].most_common(2)) for c in ('A', 'E', 'I', 'O', 'U') if vow[c]))
