"""The strict switch in the embed (and the lab page): check a take, read the words, switch strict on, read again.
On a clean take every 'not sure' becomes 'not clear' (✕) and nothing else moves; on an unclear take the marks stay and the
summary asks for a clearer take; off again restores the first view exactly; the switch is remembered on reload.
Needs the local server on 7861 and the demo site on 8099."""
import asyncio, os, sys, json
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
CASES = [('demo_th23.html', 'take_alouf_23_1_swap.wav'), ('demo_th23.html', 'take_alouf_23_1_swap01.wav'), ('demo_th23.html', 'take_alouf_23_1.wav'), ('demo_th23.html', 'take_alouf_23_1_skip.wav'), ('demo_pz200.html', 'take_shrem_l2.m4a'), ('demo_th23.html', 'take_noise.wav')]
VIEW = """()=>({say: document.querySelector('.dk [data-r=say]').textContent, cls: document.querySelector('.dk [data-r=say]').className,
  w: [...document.querySelectorAll('.dk .dk-w')].map(b => [b.className.replace('dk-w','').replace('sel','').trim(), b.querySelector('small').textContent, [...b.querySelectorAll('b span')].map(s => s.className).join(',')]),
  notes: document.querySelector('.dk [data-r=notes]').textContent, strict: document.querySelector('.dk [data-r=strict]').checked})"""
fails = []
async def one(pw, page, take):
    b = await pw.chromium.launch(); c = await b.new_context(viewport={'width': 390, 'height': 844}); P = await c.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
    got = {}
    async def on_resp(r):
        if '/job/' in r.url or r.url.split('?')[0].endswith('/check'):
            try:
                j = await r.json()
                if 'take' in j: got['j'] = j
                elif isinstance(j.get('result'), dict) and 'take' in j['result']: got['j'] = j['result']
            except Exception: pass
    P.on('response', on_resp)
    await P.goto(f'http://127.0.0.1:8099/{page}'); await P.evaluate("()=>{try{localStorage.removeItem('dk.strict')}catch(e){}}"); await P.reload(); await P.wait_for_timeout(2500)
    files = await P.query_selector_all('.dk input[type=file]'); await files[0].set_input_files(os.path.join(HERE, take)); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
    await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}", timeout=300000)
    v0 = await P.evaluate(VIEW)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(300); v1 = await P.evaluate(VIEW)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(300); v2 = await P.evaluate(VIEW)
    await P.click('.dk [data-r=strict]'); await P.wait_for_timeout(200); await P.reload(); await P.wait_for_timeout(1500)
    kept = await P.evaluate("()=>document.querySelector('.dk [data-r=strict]').checked")
    j = got.get('j'); hs = sorted(t['hskel'] for t in j['take']['words'] if (t.get('n') or 0) >= 2 and t.get('hskel') is not None) if j else []
    if len(hs) >= 3: hs = hs[1:]
    hm = hs[(len(hs) - 1) // 2] if hs else None; clean = hm is not None and hm >= .7
    print(f'\n== {take} on {page}: clean {clean} (head {hm})')
    for name, v in (('lenient', v0), ('strict', v1)):
        print(f'  {name:8s} [{v["cls"]}] {v["say"][:110]}'); print('           ', ' '.join(f'{m}:{l}' for m, l, _ in v['w']))
    if errs: fails.append((take, 'page errors', errs))
    if v2 != v0: fails.append((take, 'switching off did not restore the first view'))
    if not kept: fails.append((take, 'the switch was not remembered on reload'))
    m0 = [m for m, _, _ in v0['w']]; m1 = [m for m, _, _ in v1['w']]
    nospeech = 'did not hear any singing' in v0['say']; canthear = 'could not make out' in v0['say']
    if clean and not canthear and not nospeech:
        if 'unsure' in m1: fails.append((take, 'strict left a not-sure word on a clean take'))
        if any(a != b and not (a == 'unsure' and b == 'off') for a, b in zip(m0, m1)): fails.append((take, 'strict moved something other than not-sure', m0, m1))
        if 'not clear enough for a strict check' in v1['say']: fails.append((take, 'unclear banner on a clean take'))
    else:
        if m0 != m1: fails.append((take, 'strict changed marks on an unclear take', m0, m1))
        if not nospeech and not canthear and 'wrong' not in v0['cls'] and 'does not sound like this line' not in v0['say'] and 'not clear enough for a strict check' not in v1['say']:
            fails.append((take, 'no "not clear enough" on an unclear take', v1['say']))
    await b.close()
async def main():
    async with async_playwright() as pw:
        for page, take in CASES: await one(pw, page, take)
        # the lab page: the switch is there and toggles without errors (no take)
        b = await pw.chromium.launch(); P = await b.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto('http://127.0.0.1:7861/'); await P.wait_for_timeout(2000); n = await P.evaluate("()=>!!document.getElementById('strict')")
        print('\nlab page: switch present', n, '| errors', errs)
        if not n or errs: fails.append(('lab page', n, errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
