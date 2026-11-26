"""The Name read "Elohim" (אֲדֹנָי יֱהֹוִה), before and after v6.0's reading of it: what the checker says about that
word in a correct reader's take — its mark, how well the heads heard it, the vowel notes on it.
  name_check.py tehillim <lab> <reader>     the reader's own takes of the Tehillim pesukim that carry it (those he has),
                                            with Rabbi Alouf as the hazzan — and Rabbi Alouf's own, as the reader
  name_check.py exam <exam name>            an exam of such pesukim kept by bench/exam_items.py (lt_jobs.py ELOHIM=only)
env: DK_URL (the server asked: an old one and a new one give the before and the after), DK_LAB_V"""
import sys, os, json, subprocess, requests
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import rule, nikud as NK
BASE = os.environ.get('DK_URL', 'http://127.0.0.1:7861')
def name_words(nik): return [i for i, (w, _, _) in enumerate(NK.parse_verse(nik)) if NK.name_elohim(w)]
def say(label, out, nik):
    sm = rule.summarize(out); TW = out['take']['words']
    for i in name_words(nik):
        notes = [(v['you'], v['ref'], v['against']) for v in sm['vowels'] if v['i'] == i]
        raw = [(d['you'], d['ref']) for k in ('vowels', 'vowels_nikud') for d in (out.get(k) or {}).get(str(i), [])]
        print(f"  {label:28s} {out['words'][i]:6s} {sm['marks'][i]:6s} letter head {TW[i].get('hskel')}, vowel head {TW[i].get('vskel')}, kept {TW[i].get('kept')}, pw {TW[i].get('pw')} | notes shown {notes} (the ear gave {raw})")
        yield sm['marks'][i], len(notes), len(raw)
def cut(path, a, b):
    return subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, a):.3f}', '-i', path, '-t', f'{b - a:.3f}', '-ac', '1', '-ar', '16000', '-f', 'wav', '-'], capture_output=True, timeout=120).stdout
res = []
if sys.argv[1] == 'tehillim':
    LAB, WHO = sys.argv[2:4]; IDX = json.load(open(os.path.join(LAB, 'out', 'tehillim-alouf', 'tehillim_alouf.json'), encoding='utf-8'))['perakim']
    for n, R in sorted(IDX.items(), key=lambda x: int(x[0])):
        for i, q in enumerate(R['pesukim']):
            if not name_words(q['nikud']): continue
            alts = '|'.join(x['text'] for k, x in enumerate(R['pesukim']) if k != i and x.get('text')); prm = {'words': q['text'], 'nikud': q['nikud'], 'alts': alts}
            if q['t0'] is not None:   # Rabbi Alouf himself as the reader (his recording of the pasuk, no hazzan)
                wav = cut(os.path.join(ROOT, 'static', 'tehillim', R['file']), q['t0'], q['t1'])
                out = requests.post(BASE + '/check', params=prm, data=wav, headers={'Content-Type': 'application/octet-stream'}, timeout=900).json()
                res += list(say(f'{n}:{i + 1} Rabbi Alouf', out, q['nikud']))
            ap = os.path.join(LAB, f'out_{WHO}', 'align', f'{n}.json')
            if os.path.exists(ap):
                A = json.load(open(ap, encoding='utf-8')); p = A['pesukim'][i]
                if p['t0'] is not None:
                    wav = cut(os.path.join(LAB, f'data_{WHO}', f'{int(n):03d}.mp3'), p['t0'] - .25, p['t1'] + .25)
                    if q['t0'] is not None: prm = dict(prm, ref=R['file'], t0=q['t0'], t1=q['t1'])
                    out = requests.post(BASE + '/check', params=prm, data=wav, headers={'Content-Type': 'application/octet-stream'}, timeout=900).json()
                    res += list(say(f'{n}:{i + 1} {WHO}', out, q['nikud']))
else:
    V = os.environ.get('DK_LAB_V') or '.'
    for l in open(os.path.join(V, f'exam_{sys.argv[2]}.full.jsonl'), encoding='utf-8'):
        r = json.loads(l); res += list(say(r['id'], r['out'], r['nikud']))
import collections
c = collections.Counter(m for m, _, _ in res)
print(f"{len(res)} Names read Elohim: ✓ {c['ok']}, not sure {c['unsure']}, red {c['off']}; with a vowel note shown {sum(1 for _, n, _ in res if n)}; with a note from the ear {sum(1 for _, _, n in res if n)}")
