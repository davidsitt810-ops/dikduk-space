"""A score out of 100 for each reader: how closely his reading matches what the checker expects of a proper Sephardic
reading (the written text, ע/ח from the throat, the nikud's vowels, the shva rules), and how sure the checker is.
From an exam (exam_voice.py rows, hazzan = Rabbi Alouf) and the reader's alignment:
  throat  30%  share of his ע and ח the checker hears from the throat
  vowels  25%  1 - vowel notes per vowel he said (a note = the vowel ear heard another vowel than the nikud's / the hazzan's)
  shva    15%  1 - shva notes per shva in the text
  words   20%  share of words the checker confirms (✓)
  clarity 10%  how cleanly the audio fits the text's sounds (mean unit probability of the forced alignment)
Sure (0-100) = share of takes the checker hears clearly (head median >= .7) x a size factor (1 at 1,500 words, ~.5 at 200),
lowered further when the alignment itself is shaky (mean unit probability under .6).
Also a score per pasuk on the same parts, so the best pesukim can be picked for training.
usage: score_voice.py <name>=<exam json>,<align dir> ...   (writes score_<name>.json with the per-pasuk scores)"""
import sys, os, json, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
SHEVA = 'ְ'
W = {'throat': .30, 'vowels': .25, 'shva': .15, 'words': .20, 'clarity': .10}
def vowel_count(nikud):   # vowel marks said (sheva left out), dagesh-free; holam vav / shuruk counted once
    return len(re.findall('[ֱ-ׇֻ]', nikud)) + len(re.findall('וּ(?![ְ-ׇֻ])', nikud))
out_rows = []
for spec in sys.argv[1:]:
    name, rest = spec.split('=', 1); ex, al = rest.split(',', 1)
    R = [r for r in json.load(open(ex, encoding='utf-8')) if 'words' in r]
    A = {}
    tot = collections.Counter(); per = []
    for r in R:
        n = r['per']
        if n not in A: A[n] = json.load(open(os.path.join(al, f'{n}.json'), encoding='utf-8'))
        p = A[n]['pesukim'][r['ps']]; nik = p.get('nikud') or ''
        words = len(r['marks']); ok = sum(m == 'ok' for m in r['marks'])
        th = [t for t in r['throat'] if t['c'] in 'עח']; th_ok = sum(t['v'] == 'throat' for t in th)
        vn = len({(v['w'], v['k']) for v in r['vowels']}); vc = max(1, vowel_count(nik))
        sn = len(r['shva']); sc = nik.count(SHEVA)
        part = {'throat': th_ok / len(th) if th else None, 'vowels': max(0.0, 1 - vn / vc), 'shva': max(0.0, 1 - sn / sc) if sc else None,
                'words': ok / words if words else None, 'clarity': p['p']}
        have = {k: v for k, v in part.items() if v is not None}
        score = 100 * sum(W[k] * v for k, v in have.items()) / sum(W[k] for k in have)
        per.append({'reader': name, 'per': n, 'ps': r['ps'] + 1, 'score': round(score, 1), 'clean': r['clean'], **{k: (round(v, 3) if v is not None else None) for k, v in part.items()}})
        tot['words'] += words; tot['ok'] += ok; tot['th'] += len(th); tot['th_ok'] += th_ok; tot['vn'] += vn; tot['vc'] += vc; tot['sn'] += sn; tot['sc'] += sc
        tot['clean'] += r['clean']; tot['takes'] += 1; tot['p'] += p['p']
    if not tot['takes']: continue
    parts = {'throat': tot['th_ok'] / max(1, tot['th']), 'vowels': 1 - tot['vn'] / max(1, tot['vc']), 'shva': 1 - tot['sn'] / max(1, tot['sc']),
             'words': tot['ok'] / max(1, tot['words']), 'clarity': tot['p'] / tot['takes']}
    score = 100 * sum(W[k] * v for k, v in parts.items())
    clean = tot['clean'] / tot['takes']; size = min(1.0, (tot['words'] / 1500) ** .35); shaky = min(1.0, parts['clarity'] / .6)
    sure = 100 * clean * size * shaky
    good = [q for q in per if q['score'] >= 90 and q['clean']]
    print(f"{name:10s} score {score:5.1f}/100  sure {sure:3.0f}/100  | throat {100 * parts['throat']:.0f}  vowels {100 * parts['vowels']:.0f}  shva {100 * parts['shva']:.0f}"
          f"  words {100 * parts['words']:.1f}  clarity {100 * parts['clarity']:.0f}  | {tot['takes']} pesukim, {tot['words']} words, clean {100 * clean:.0f}%"
          f"  | pesukim scoring 90+ and clear: {len(good)} ({100 * len(good) / len(per):.0f}%)")
    json.dump(per, open(os.path.join(HERE, f'score_{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
