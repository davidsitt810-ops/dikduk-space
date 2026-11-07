"""calibration curve: correct-reading false notes (bigA+bigB) vs sparse planted i-for-e told (oneie), per variant"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C, rules as RU
V = C.V
corr = RU.load(V, 'samra_bigA+samra_bigB'); one = RU.load(V, 'samra_oneie')
base_c = C.count(corr); base_o = C.count(one)
print(f'{"variant":34s} {"false words (13,498)":>22s} {"planted told (478)":>20s} {"clean (444)":>12s} {"others (3,576)":>14s}')
for v in sys.argv[1:]:
    kw = C.parse(v); c = C.count(corr, **kw) if kw else base_c; o = C.count(one, **kw) if kw else base_o
    print(f'{v:34s} {c[2]:6d} = {100*c[2]/c[3]:.2f}%        {o[0]:4d} = {100*o[0]/o[1]:.1f}%   {100*o[4]/o[5]:5.1f}%    {o[2]:4d} = {100*o[2]/o[3]:.1f}%')
