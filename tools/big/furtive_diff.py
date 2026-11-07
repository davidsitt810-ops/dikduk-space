"""Exactly which words the furtive fix changes, per exam: notes removed, notes added, planted words lost."""
import sys, os, json
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(V, 'big'))
import rules as RU
for spec in sys.argv[1:]:
    nm, _, rng = spec.partition(':'); lo, hi = (int(x) for x in (rng or '1-150').split('-'))
    rows = RU.load(V, nm, lo, hi); rem = add = lost = 0; ex_add = []; ex_lost = []
    for r in rows:
        a = RU.noted(r); b = RU.noted(r, furtive=True); P = set(r.get('planted') or [])
        rem += len((a - b) - P); add += len((b - a) - P)
        for i in (b - a) - P: ex_add.append((r['per'], r.get('ps'), r['words'][i]))
        for i in P & (a - b):
            if r['marks'][i] != 'off': lost += 1; ex_lost.append((r['per'], r.get('ps'), r['words'][i]))
    print(f'{spec}: false notes removed {rem}, added {add}; planted words no longer told {lost}')
    for e in ex_add[:8]: print('   added', e)
    for e in ex_lost[:8]: print('   lost', e)
