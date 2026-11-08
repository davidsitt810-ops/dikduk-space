"""v5.7 in the embed: the vowel notes on a take clear enough for them (rule.vclean_of: clean, or the letter head's median
>= .62 with the line gap <= .17 on a line with nikud) and the too-noisy hint (rule.summarize 'noisy': the take's noise estimate under 26 dB
where it lost its vowel check or its words). Each take is checked on the demo site; from the server's own JSON the
test works out what the page must show, and compares: the hint shown or not, the vowel notes present only when the
gate is open. The takes: Rabbi Alouf's 23:1 as recorded, through a phone in a room, and with the noise 10 dB under
(exam_voice.py's DEGRADE, seed 23001). Needs the local server on 7861 and the demo site on 8099."""
import asyncio, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import rule
CASES = [('demo_th23.html', 'take_alouf_23_1.wav'), ('demo_th23.html', 'take_alouf_23_1_phone.wav'), ('demo_th23.html', 'take_alouf_23_1_noisy.wav')]
VIEW = """()=>({say: document.querySelector('.dk [data-r=say]').textContent, noisy: document.querySelector('.dk [data-r=noisy]').hidden ? null : document.querySelector('.dk [data-r=noisy]').textContent,
  notes: document.querySelector('.dk [data-r=notes]').textContent})"""
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
    await P.goto(f'http://127.0.0.1:8099/{page}'); await P.wait_for_timeout(2500)
    files = await P.query_selector_all('.dk input[type=file]'); await files[0].set_input_files(os.path.join(HERE, take)); await P.wait_for_timeout(300); await P.click('.dk [data-r=check]')
    await P.wait_for_function("()=>{const b=document.querySelector('.dk [data-r=busy]');return b&&b.hidden===true&&document.querySelector('.dk [data-r=say]').textContent}", timeout=300000)
    v = await P.evaluate(VIEW); j = got.get('j')
    if not j: fails.append((take, 'no result JSON seen')); await b.close(); return
    TW = j['take']['words']; clean = rule.clean_of(TW); vclean = rule.vclean_of(TW, j['take'].get('gap'), clean, j.get('vowels_nikud') is not None)
    sm = rule.summarize(j); snr = j['take'].get('snr')
    print(f"\n== {take}: head {rule.head_median(TW)}, gap {j['take'].get('gap')}, snr {snr} dB, clean {clean}, vowel gate {vclean}, server says noisy {sm['noisy']}")
    print(f"   say: {v['say'][:120]}\n   noisy hint: {v['noisy']}\n   notes: {v['notes'][:160]}")
    if errs: fails.append((take, 'page errors', errs))
    if snr is None: fails.append((take, 'no snr in the take (server before v5.7?)'))
    if bool(v['noisy']) != sm['noisy']: fails.append((take, 'the page and the server disagree on the noise hint', v['noisy'], sm['noisy']))
    if not vclean and sm['vowels']: fails.append((take, 'vowel notes with the gate shut'))
    if sm['vowels'] and 'where the' not in v['notes']: fails.append((take, 'server vowel notes not shown', sm['vowels']))
    if not sm['vowels'] and 'where the hazzan sings' in v['notes'] or (not sm['vowels'] and 'where the nikud says' in v['notes']): fails.append((take, 'a vowel note the server did not give'))
    await b.close()
async def main():
    async with async_playwright() as pw:
        for page, take in CASES: await one(pw, page, take)
        b = await pw.chromium.launch(); P = await b.new_page(); errs = []; P.on('pageerror', lambda e: errs.append(str(e)))
        await P.goto('http://127.0.0.1:7861/'); await P.wait_for_timeout(2000)
        n = await P.evaluate("()=>[!!document.getElementById('noisy'), !!document.getElementById('learn'), !!document.getElementById('meP')]")
        print('\nlab page: noise hint / learn switch / voice panel present', n, '| errors', errs)
        if not all(n) or errs: fails.append(('lab page', n, errs))
        await b.close()
    print('\nFAILS:' if fails else '\nALL GOOD', *fails, sep='\n  '); sys.exit(1 if fails else 0)
asyncio.run(main())
