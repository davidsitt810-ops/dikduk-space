"""ONLY_PS lists for a calibrated head's exams: the takes of a finished exam from perek <lo> on (perek:pasuk from 1).
usage: pslist.py <exam name> <lo> <out file>"""
import sys, os, json
V = (os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
nm, lo, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
rows = json.load(open(os.path.join(V, f'exam_{nm}.json'), encoding='utf-8'))
ps = sorted({(r['per'], r['ps'] + 1) for r in rows if r['per'] >= lo and 'err' not in r})
open(out, 'w').write(','.join(f'{a}:{b}' for a, b in ps)); print(nm, len(ps), 'takes from perek', lo)
