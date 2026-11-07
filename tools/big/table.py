"""One row per rule variant: false notes on the correct readers, and the planted mistakes told (one per pasuk), each
replayed from the raw slots on the same takes. Columns that have no exam yet are left out.
usage: table.py [--md] <variant> ...      (variants as in compare.py; "-" = the live v5.5)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C, rules as RU
V = C.V
COLS = [('Faraj 1–55 false', 'samra_bigA', 'false'), ('Faraj 56–150 false', 'samra_bigB', 'false'),
        ('Shmuelof false', 'shmuelof_big', 'false'),
        ('i for e', 'samra_oneie', 'told'), ('e for i', 'samra_oneei', 'told'), ('e for a', 'samra_oneea', 'told'),
        ('u for o', 'samra_oneuo', 'told'), ('o for u', 'samra_oneou', 'told'),
        ('Shm. i for e', 'shmuelof_oneie', 'told'), ('Shm. e for i', 'shmuelof_oneei', 'told'), ('Shm. e for a', 'shmuelof_oneea', 'told'),
        ('Shm. u for o', 'shmuelof_oneuo', 'told'), ('Shm. o for u', 'shmuelof_oneou', 'told')]
md = '--md' in sys.argv; vs = [a for a in sys.argv[1:] if a != '--md']
data = {nm: RU.load(V, nm) for _, nm, _ in COLS}
cols = [c for c in COLS if data[c[1]]]
if md: print('| variant | ' + ' | '.join(c[0] for c in cols) + ' |'); print('|---' * (len(cols) + 1) + '|')
else: print(f'{"variant":40s}' + ''.join(f'{c[0]:>18s}' for c in cols))
for v in vs:
    kw = C.parse(v); cells = []
    for name, nm, what in cols:
        t = C.count(data[nm], **kw)
        cells.append(f'{100 * t[2] / t[3]:.2f}%' if what == 'false' else f'{100 * t[0] / t[1]:.1f}%')
    if md: print(f'| {v} | ' + ' | '.join(cells) + ' |')
    else: print(f'{v:40s}' + ''.join(f'{c:>18s}' for c in cells))
