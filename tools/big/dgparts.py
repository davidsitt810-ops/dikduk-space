"""The phone's parts (exam_voice.py DEGRADE=...) on the same takes of Faraj's correct reading, against the takes as
recorded (samra_v56B): clean takes, the letter head's median, the words "not sure" / red / with a vowel note, ע and ח.
usage: dgparts.py <exam> ...   (exams run on the ps56_oneei list, with the hazzan)"""
import sys, os, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RU, drops as D
V = D.V
A = {(r['per'], r['ps']): r for r in RU.load(V, 'samra_v56B', 56, 150)}
def row(name):
    B = {(r['per'], r['ps']): r for r in RU.load(V, name, 56, 150)}; keys = sorted(set(A) & set(B)) if name != 'samra_v56B' else None
    if keys is None: return None
    out = {}
    for nm, R in (('a', A), ('b', B)):
        rs = [R[k] for k in keys]; W = sum(len(r['marks']) for r in rs)
        th = collections.Counter((t['c'], t['v']) for r in rs for t in (r.get('throat') or []))
        out[nm] = dict(n=len(rs), clean=sum(r['clean'] for r in rs), head=st.median([r['head'] for r in rs if r.get('head') is not None]),
                       unsure=sum(m == 'unsure' for r in rs for m in r['marks']), red=sum(m == 'off' for r in rs for m in r['marks']), W=W,
                       noted=sum(len(RU.noted(r, furtive=True)) for r in rs),
                       ayin=th[('ע', 'throat')] / max(1, sum(v for (c, _), v in th.items() if c == 'ע')),
                       het=th[('ח', 'throat')] / max(1, sum(v for (c, _), v in th.items() if c == 'ח')))
    return out
first = True
for name in sys.argv[1:]:
    o = row(name)
    if first:
        a = o['a']; print(f"{'as recorded':22s} takes {a['n']}  clean {100*a['clean']/a['n']:5.1f}%  head median {a['head']:.3f}  not sure {100*a['unsure']/a['W']:4.1f}%  red {a['red']}  noted {100*a['noted']/a['W']:4.1f}%  ע throat {100*a['ayin']:4.1f}%  ח throat {100*a['het']:4.1f}%"); first = False
    b = o['b']; print(f"{name:22s} takes {b['n']}  clean {100*b['clean']/b['n']:5.1f}%  head median {b['head']:.3f}  not sure {100*b['unsure']/b['W']:4.1f}%  red {b['red']}  noted {100*b['noted']/b['W']:4.1f}%  ע throat {100*b['ayin']:4.1f}%  ח throat {100*b['het']:4.1f}%")
