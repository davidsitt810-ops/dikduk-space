"""v6.0: the "your vowels were not checked" / "only partly checked" line (rule.summarize 'vlost' / 'vpart'), on the lab
page and in the embed. A take that is not clear enough for the vowel notes and has no background noise to blame used
to show nothing about vowels at all — as if they had passed. Now a line with nikud (Tehillim) is PARTLY checked on such
a take — the notes the phone ear confirms show (rule.note_shown) — and the page says so; a line without nikud (or a
server before v6.0) is NOT checked, and the page says that.
The unclear take is made here, not kept in the repo: Rabbi Alouf's 23:1 played as a tape 1.85 times too fast (ffmpeg
asetrate) — the letter head hears it at about .47, the line gap is about .45, the noise estimate stays near 31 dB: not
clean, the vowel gate shut, not noisy, the words still made out.
From the server's own JSON the test works out what must show (rule.summarize) and compares, on both pages:
  the unclear take      -> "only partly checked", no noise line; only notes rule.summarize shows
  the same, sent without the nikud (the request rewritten on its way: a line with a hazzan and no nikud)
                        -> "not checked", no vowel notes; in the lab's vowel panel "not checked"
  the take as recorded  -> no line
  the noisier take      -> the noise line, saying "only partly checked"; not this line (never both)
  strict on (unclear)   -> the strict line asks for a clearer take; this line is hidden
  embed, vowel notes turned off -> hidden (nothing the person asked for was lost)
Needs ffmpeg, the local server on 7861 (this checkout) and the demo site on 8099 (tools/bench/demo_site.sh)."""
import asyncio, os, subprocess, sys, tempfile
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import rule
TMP = tempfile.mkdtemp(prefix='dk_vlost_'); UNCLEAR = os.path.join(TMP, 'take_unclear.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(HERE, 'take_alouf_23_1.wav'), '-af', 'asetrate=16000*1.85,aresample=16000', '-ac', '1', UNCLEAR], check=True)
CLEAR = os.path.join(HERE, 'take_alouf_23_1.wav'); NOISIER = os.path.join(HERE, 'take_alouf_23_1_noisier.wav')
LINE = {'vlost': 'Your vowels were not checked this time', 'vpart': 'Your vowels were only partly checked this time'}
NO_NIKUD = {'on': False}
async def strip_nikud(route):
    """the check sent without its nikud (while NO_NIKUD is on): the server then has a hazzan and no nikud, as for a pizmon"""
    u = urlsplit(route.request.url)
    if NO_NIKUD['on'] and u.path.endswith('/check'):
        q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k != 'nikud']
        await route.continue_(url=urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), u.fragment)))
    else: await route.continue_()
fails = []
def need(ok, *what):
    if not ok: fails.append(what)
    print('  ', 'ok ' if ok else 'BAD', *what)
def catcher(P, got):
    async def on_resp(r):
        if '/job/' in r.url or r.url.split('?')[0].endswith('/check'):
            try:
                j = await r.json(); j = j.get('result') if isinstance(j.get('result'), dict) else j
                if isinstance(j, dict) and 'take' in j: got['j'] = j
            except Exception: pass
    P.on('response', on_resp)
def facts(j):
    sm = rule.summarize(j); TW = j['take']['words']
    print(f"     server: head {rule.head_median(TW)}, gap {j['take'].get('gap')}, snr {j['take'].get('snr')} dB, clean {sm['clean']}, vowels checked {sm['vclean']}, noisy {sm['noisy']}, vlost {sm['vlost']}, can't hear {sm['cant_hear']}, line wrong {sm['line_wrong']}")
    return sm
def judge(where, name, v, sm, want):
    got = {k: sm[k] for k in ('vlost', 'vpart', 'noisy')}
    need(got == want, f'{where}, {name}: the server says {got}', 'wanted', want)
    line = 'vlost' if sm['vlost'] else 'vpart' if (sm['vpart'] and not sm['noisy']) else None   # which line must show (the noise line says "partly" itself)
    need((v['vlost'] is not None) == (line is not None), f'{where}, {name}: the line shows exactly when the server says so', v['vlost'])
    need((v['noisy'] is not None) == sm['noisy'], f'{where}, {name}: the noise line as the server says', v['noisy'])
    need(not (v['vlost'] and v['noisy']), f'{where}, {name}: never both lines')
    if line: need(LINE[line] in (v['vlost'] or ''), f'{where}, {name}: the words of the line ({line})', v['vlost'])
    if sm['noisy'] and not sm['cant_hear']: need(('only partly checked' in v['noisy']) == sm['vpart'] and ('not checked' in v['noisy']) == (not sm['vpart']), f'{where}, {name}: the noise line says partly / not checked as the server does', v['noisy'])
    need(len(v['vow']) == len({x['i'] for x in sm['vowels']}), f'{where}, {name}: a vowel line for each word the server notes, no other', len(v['vow']), sorted({x['i'] for x in sm['vowels']}))
    if sm['vlost']: need(not v['vow'], f'{where}, {name}: no vowel notes', v['vow'])

async def lab(pw):
    print('the lab page:')
    b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page()
    errs = []; P.on('pageerror', lambda e: errs.append(str(e))); got = {}; catcher(P, got); await P.route('**/check*', strip_nikud)
    VIEW = """()=>({say:document.querySelector('#say').textContent, noisy:document.querySelector('#noisy').hidden?null:document.querySelector('#noisy').textContent,
       vlost:document.querySelector('#vlost').hidden?null:document.querySelector('#vlost').textContent, vw:document.querySelector('#vw')?document.querySelector('#vw').textContent:'',
       vow:[...document.querySelectorAll('#notes li')].map(l=>l.textContent).filter(t=>/where the (hazzan|nikud)/.test(t))})"""
    async def check(path):
        if await P.evaluate("()=>!document.querySelector('#s4').hidden"): await P.click('#againLine'); await P.wait_for_timeout(300)
        got.pop('j', None); await P.set_input_files('#file', path); await P.wait_for_timeout(300); await P.click('#check')
        await P.wait_for_function("()=>document.querySelector('#busy').hidden===true&&document.querySelector('#say').textContent", timeout=300000); await P.wait_for_timeout(800)
        return await P.evaluate(VIEW), got.get('j')
    await P.goto('http://127.0.0.1:7861/?th=23&line=1'); await P.evaluate("()=>{try{localStorage.removeItem('dk.strict')}catch(e){}}"); await P.reload(); await P.wait_for_timeout(3000)
    for name, path, want in (('unclear', UNCLEAR, {'vlost': False, 'vpart': True, 'noisy': False}), ('unclear, no nikud', UNCLEAR, {'vlost': True, 'vpart': False, 'noisy': False}),
                             ('as recorded', CLEAR, {'vlost': False, 'vpart': False, 'noisy': False}), ('noisier', NOISIER, {'vlost': False, 'vpart': True, 'noisy': True})):
        NO_NIKUD['on'] = name.endswith('no nikud')
        v, j = await check(path)
        if not j: need(False, f'lab, {name}: no result JSON seen'); continue
        sm = facts(j); judge('lab', name, v, sm, want)
        if name == 'unclear, no nikud': need('not checked' in v['vw'] and 'No clear vowel differences' not in v['vw'], 'lab, unclear, no nikud: the vowel panel says not checked, not "no differences"', v['vw'][:90])
        if name == 'unclear' and not sm['vowels']: need('not clear enough for a full vowel check' in v['vw'], 'lab, unclear: the vowel panel says not a full check', v['vw'][:90])
        if name == 'as recorded': need('not checked' not in v['vw'], 'lab, as recorded: the vowel panel as before', v['vw'][:90])
    NO_NIKUD['on'] = False; v, j = await check(UNCLEAR)
    await P.click('#strict'); await P.wait_for_timeout(600); v2 = await P.evaluate(VIEW)
    need(v['vlost'] is not None and v2['vlost'] is None and 'strict check' in v2['say'], 'lab, unclear with strict on: the strict line instead of this one', v2['say'][:80], v2['vlost'])
    await P.click('#strict'); await P.wait_for_timeout(600); v3 = await P.evaluate(VIEW)
    need(v3['vlost'] is not None, 'lab, strict off again: the line is back')
    need(not errs, 'lab: no page errors', errs); await b.close()

async def embed(pw):
    print('the embed (demo site):')
    b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page()
    errs = []; P.on('pageerror', lambda e: errs.append(str(e))); got = {}; catcher(P, got); await P.route('**/check*', strip_nikud)
    q = lambda r: f"document.querySelector('.dk [data-r={r}]')"
    VIEW = f"""()=>({{say:{q('say')}.textContent, noisy:{q('noisy')}.hidden?null:{q('noisy')}.textContent, vlost:{q('vlost')}.hidden?null:{q('vlost')}.textContent,
       vow:[...document.querySelectorAll('.dk [data-r=notes] li')].map(l=>l.textContent).filter(t=>/where the (hazzan|nikud)/.test(t))}})"""
    async def check(path):
        if await P.evaluate(f"()=>!{q('s4')}.hidden"): await P.click('.dk [data-r=againLine]'); await P.wait_for_timeout(300)
        got.pop('j', None); files = await P.query_selector_all('.dk input[type=file]'); await files[0].set_input_files(path); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
        await P.wait_for_function(f"()=>{{const b={q('busy')};return b&&b.hidden===true&&{q('say')}.textContent}}", timeout=300000); await P.wait_for_timeout(800)
        return await P.evaluate(VIEW), got.get('j')
    await P.goto('http://127.0.0.1:8099/demo_th23.html'); await P.evaluate("()=>{try{localStorage.removeItem('dk.strict');localStorage.removeItem('dk.notes')}catch(e){}}"); await P.reload(); await P.wait_for_timeout(2500)
    for name, path, want in (('unclear', UNCLEAR, {'vlost': False, 'vpart': True, 'noisy': False}), ('unclear, no nikud', UNCLEAR, {'vlost': True, 'vpart': False, 'noisy': False}),
                             ('as recorded', CLEAR, {'vlost': False, 'vpart': False, 'noisy': False}), ('noisier', NOISIER, {'vlost': False, 'vpart': True, 'noisy': True})):
        NO_NIKUD['on'] = name.endswith('no nikud')
        v, j = await check(path)
        if not j: need(False, f'embed, {name}: no result JSON seen'); continue
        sm = facts(j); judge('embed', name, v, sm, want)
    NO_NIKUD['on'] = False; v, j = await check(UNCLEAR)
    on = await P.evaluate(f"()=>{q('nVow')}.checked")
    if not on: await P.click('.dk [data-r=nVow]'); await P.wait_for_timeout(500); v = await P.evaluate(VIEW)
    need(v['vlost'] is not None, 'embed, unclear, vowel notes on: the line shows')
    await P.click('.dk [data-r=nVow]'); await P.wait_for_timeout(500); v2 = await P.evaluate(VIEW)
    need(v2['vlost'] is None, 'embed, vowel notes turned off: the line is hidden', v2['vlost'])
    await P.click('.dk [data-r=nVow]'); await P.wait_for_timeout(500)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(600); v3 = await P.evaluate(VIEW)
    need(v3['vlost'] is None and 'strict check' in v3['say'], 'embed, unclear with strict on: the strict line instead of this one', v3['say'][:80])
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(600); v4 = await P.evaluate(VIEW)
    need(v4['vlost'] is not None, 'embed, strict off again: the line is back')
    need(not errs, 'embed: no page errors', errs); await b.close()

async def main():
    async with async_playwright() as pw:
        await lab(pw); await embed(pw)
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
