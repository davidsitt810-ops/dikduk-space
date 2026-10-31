"""How strict mode (every 'not sure' word counts as 'not clearly right') changes the line checker's verdicts on the
exam rows (Alouf + archive takes, with known truth): false alarms on intact lines vs. catches on broken ones."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, '..', 'space', 'app.py'), encoding='utf-8').read()
def pyfn(name, stop): i = src.index(f'def {name}('); j = src.index(stop, i); return src[i:j]
code = 'import numpy as np\n' + src[src.index("RULE = {'drop'"):src.index('\ndef head_median')] + '\n' + pyfn('mark_of', '\nRULE = ') + pyfn('head_median', '\ndef clean_of') + pyfn('clean_of', '\ndef marks_of') + pyfn('marks_of', '\ndef summarize')
ns = {}; exec(code, ns)
for f in sys.argv[1:] or ['exam_rows.json', 'exam_archive_rows.json']:
    R = json.load(open(os.path.join(HERE, f), encoding='utf-8')); L = collections.defaultdict(dict)
    for r in R: L[(r['case'], r.get('per', r.get('pid', r.get('f'))), r.get('ps', r.get('line', 0)), r.get('rec', ''))][r['k']] = r
    S = collections.defaultdict(lambda: collections.Counter())
    for key, d in L.items():
        TW = [d[k] for k in sorted(d)]; F = [{'fit': t.get('fit')} for t in TW] if any(t.get('fit') is not None for t in TW) else None
        rv = {'gain': TW[0]['rival']} if TW[0].get('rival') is not None else None
        clean = ns['clean_of'](TW); marks, why, lw, cant = ns['marks_of'](TW, F, TW[0].get('gap'), clean, rv)
        for mode in ('lenient', 'strict'):
            m = [('off' if x == 'unsure' else x) for x in marks] if mode == 'strict' and not cant and clean else list(marks)
            c = S[(key[0], mode)]; c['lines'] += 1; c['clean takes'] += bool(clean)
            bad = [i for i, t in enumerate(TW) if t.get('bad')]
            if key[0] == 'intact' or not bad:
                c['passed (nothing flagged)'] += all(x in ('ok', '') for x in m) and not lw
                c['words flagged ✕'] += sum(x == 'off' for x in m); c['words'] += len(m)
            else:
                c['caught (bad word ✕)'] += any(m[i] == 'off' for i in bad) or lw
                c['bad word not ✓'] += any(m[i] != 'ok' for i in bad) or lw
    print('\n==', f)
    for (case, mode), c in sorted(S.items()):
        n = c['lines']
        print(f"{case:10s} {mode:8s} " + ' · '.join(f"{k} {v}/{n} ({100*v/n:.0f}%)" if k not in ('words flagged ✕', 'words') else '' for k, v in c.items() if k != 'lines' and k != 'words').strip(' ·') + (f" · good words ✕ {c['words flagged ✕']}/{c['words']} ({100*c['words flagged ✕']/max(1,c['words']):.1f}%)" if c['words'] else ''))
