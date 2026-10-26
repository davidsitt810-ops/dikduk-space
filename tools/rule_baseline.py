"""The accuracy alarm: every committed exam row through today's rules (rule.py for the words, letters.py for the letter
checker), tallied, and compared with tools/rule_baseline.json. Any change in a tally fails, and the changed numbers
are printed, so a change to a rule cannot move the measured numbers without someone deciding it should (then run
with --update and commit the new baseline with the change). No models: numpy only, seconds.
It catches changes to the RULES only. A new head or model changes the rows themselves: that needs the audio exams.
usage: rule_baseline.py [--update]"""
import sys, os, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)
import rule
import letters as LT
BASE = os.path.join(HERE, 'rule_baseline.json')

def lines_of(R):
    """rows (one per word) -> lines, keyed as tools/exam_report.py keys them"""
    L = collections.defaultdict(dict)
    for r in R: L[(r['case'], r.get('per', r.get('pid', r.get('f'))), r.get('ps', r.get('line', 0)), r.get('rec', ''))][r['k']] = r
    return [[v[i] for i in sorted(v)] for v in L.values()]

def words_suite(R):
    """per case: takes, clean / wrong line / cannot hear, and the right and the changed words by mark"""
    out = {}
    for TW in lines_of(R):
        F = [{'fit': t.get('fit')} for t in TW] if any(t.get('fit') is not None for t in TW) else None
        rival = {'gain': TW[0]['rival'], 'head': TW[0].get('rival_head')} if TW and TW[0].get('rival') is not None else None
        clean = rule.clean_of(TW); marks, why, lw, cant = rule.marks_of(TW, F, TW[0].get('gap'), clean, rival)
        c = out.setdefault(TW[0]['case'], {'takes': 0, 'clean': 0, 'line_wrong': 0, 'cant_hear': 0, 'right': collections.Counter(), 'wrong': collections.Counter()})
        c['takes'] += 1; c['clean'] += clean; c['line_wrong'] += lw; c['cant_hear'] += cant
        for t, m in zip(TW, marks):
            if (t.get('n') or 0) < 1: continue
            c['wrong' if t.get('bad') else 'right'][m or 'ok'] += 1
    return {k: {**v, 'right': dict(sorted(v['right'].items())), 'wrong': dict(sorted(v['wrong'].items()))} for k, v in sorted(out.items())}

def letters_suite(R):
    """per letter, variant and source (al = Rabbi Alouf, il = Israelis): the verdicts letters.verdict gives"""
    out = collections.defaultdict(collections.Counter)
    for r in R:
        L = LT.BY_C.get(r['c'])
        if not L: continue
        want = r.get('var') if L.get('want') else None
        out[f"{r['src']} {r['c']} {want or ''}".strip()][LT.verdict(r['c'], want, r)['v']] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}

def tally():
    T = {}
    for f in sorted(glob.glob(os.path.join(HERE, '*_rows.json'))):
        name = os.path.basename(f)
        if name.startswith('letters_rows'):
            if name == 'letters_rows.json': T[name] = letters_suite(json.load(open(f, encoding='utf-8')))   # v0/v1/vav are older studies
            continue
        T[name] = words_suite(json.load(open(f, encoding='utf-8')))
    return json.loads(json.dumps(T))   # Counters -> plain dicts, keys as strings

def diff(a, b, path=''):
    """the leaves that differ between two nested dicts, as 'path: old -> new'"""
    out = []
    for k in sorted(set(a) | set(b), key=str):
        p = f'{path}/{k}' if path else str(k)
        x, y = a.get(k), b.get(k)
        if isinstance(x, dict) and isinstance(y, dict): out += diff(x, y, p)
        elif x != y: out.append(f'{p}: {x} -> {y}')
    return out

if __name__ == '__main__':
    now = tally()
    if '--update' in sys.argv:
        json.dump(now, open(BASE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True); open(BASE, 'a').write('\n')
        print('baseline written:', ', '.join(now)); sys.exit(0)
    if not os.path.exists(BASE): print('no baseline yet: run with --update'); sys.exit(1)
    D = diff(json.load(open(BASE, encoding='utf-8')), now)
    if D:
        print(f'{len(D)} numbers changed against tools/rule_baseline.json:'); print('\n'.join('  ' + d for d in D))
        print('If the change is meant, run tools/rule_baseline.py --update and commit the new baseline with it.'); sys.exit(1)
    print('rule baseline: no change (' + ', '.join(f'{k}: {sum(c["takes"] for c in v.values()) if "takes" in next(iter(v.values()), {}) else sum(sum(c.values()) for c in v.values())}' for k, v in now.items()) + ')')
