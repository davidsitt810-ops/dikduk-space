/* Dikduk checker — drop-in for a site page.
   <div id="dikduk"></div>
   <script src="embed.js"></script>
   <script>Dikduk.mount(document.getElementById('dikduk'), {api:'https://davidsitt-pizmonim-dikduk.hf.space', pz:'200', line:3});</script>
   or simply <div data-dikduk data-api="https://…hf.space" data-pz="200" data-line="3"></div> and the script mounts it.
   Options: api (the checker server), pz | th (pizmon id | Tehillim perek), line (1-based), rec (hazzan recording file),
   lyrics (the site's lyrics object or a URL — saves a fetch), archive (base URL of the archive mp3s), onResult(result).
   Styling: everything is under .dk; colours and fonts are CSS variables on the container (--dk-bg, --dk-panel, --dk-line,
   --dk-fg, --dk-mute, --dk-accent, --dk-good, --dk-warn, --dk-bad, --dk-ink, --dk-he, --dk-ui); the site's own fonts are
   inherited unless --dk-he / --dk-ui are set. No browser storage is used. The same checker as the Space's /try page. */
(function () {
'use strict';
const CSS = `
.dk{--bg:var(--dk-bg,#2A1317);--panel:var(--dk-panel,#3A1C22);--line:var(--dk-line,#5A3038);--fg:var(--dk-fg,#F3E6CF);--mute:var(--dk-mute,#C9AE96);--gold:var(--dk-accent,#D8B060);--good:var(--dk-good,#9BD3A0);--warn:var(--dk-warn,#F2C230);--bad:var(--dk-bad,#EF7B6E);--ink:var(--dk-ink,#2A1317);--he:var(--dk-he,inherit);--ui:var(--dk-ui,inherit);
 color:var(--fg);font-family:var(--ui);font-size:16px;line-height:1.45;display:flex;flex-direction:column;gap:12px;max-width:560px;box-sizing:border-box}
.dk *{box-sizing:border-box}
.dk .dk-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.dk .dk-lede{margin:0;color:var(--mute);font-size:14px;max-width:34ch}
.dk .dk-pill{flex:none;font-size:12px;padding:4px 10px;border-radius:999px;border:1px solid var(--line);color:var(--mute);white-space:nowrap}
.dk .dk-pill.ok{border-color:var(--good);color:var(--good)}.dk .dk-pill.bad{border-color:var(--bad);color:var(--bad)}.dk .dk-pill.wait{border-color:var(--warn);color:var(--warn)}
.dk .dk-err{color:var(--bad);font-size:14px;margin:0;padding:10px 12px;border:1px solid var(--bad);border-radius:10px}.dk .dk-err:empty{display:none}
.dk .dk-step{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px}
.dk [hidden]{display:none!important}
.dk h3{font:600 19px/1.25 var(--ui);margin:0 0 12px;display:flex;align-items:center;gap:10px;color:var(--fg)}
.dk h4{font:500 14px/1.3 var(--ui);color:var(--mute);margin:14px 0 6px}
.dk .dk-n{flex:none;width:26px;height:26px;border-radius:50%;background:var(--gold);color:var(--ink);font:700 14px/26px var(--ui);text-align:center}
.dk .dk-sum{display:flex;align-items:center;gap:10px;font-size:15px;color:var(--mute)}
.dk .dk-sum .dk-n{background:transparent;color:var(--gold);border:1px solid var(--gold);line-height:24px}
.dk .dk-sum .dk-txt{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--fg)}
.dk .dk-he{font-family:var(--he);direction:rtl;unicode-bidi:isolate}
.dk .dk-link{font:500 14px var(--ui);color:var(--gold);background:none;border:0;padding:4px 2px;cursor:pointer;text-decoration:underline;text-underline-offset:3px}
.dk .dk-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.dk .dk-hint{font-size:13px;color:var(--mute);margin:8px 0 0}
.dk input[type=text],.dk select{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:11px 12px;min-width:0;min-height:46px}
.dk .dk-seg{display:flex;border:1px solid var(--line);border-radius:999px;padding:3px;margin-bottom:10px}
.dk .dk-seg button{flex:1;font:500 15px var(--ui);color:var(--mute);background:transparent;border:0;border-radius:999px;padding:9px 10px;cursor:pointer}
.dk .dk-seg button.on{background:var(--gold);color:var(--ink);font-weight:700}
.dk .dk-btn{font:500 15px var(--ui);color:var(--fg);background:transparent;border:1px solid var(--line);border-radius:999px;padding:10px 16px;min-height:44px;cursor:pointer}
.dk .dk-btn:hover{border-color:var(--gold)}.dk .dk-btn:focus-visible,.dk .dk-ln:focus-visible,.dk .dk-w:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.dk .dk-btn.gold{background:var(--gold);color:var(--ink);border-color:var(--gold);font-weight:700}
.dk .dk-btn.rec{background:var(--bad);color:#fff;border-color:var(--bad);font-weight:700;font-size:17px;min-height:54px}
.dk .dk-btn.wide{width:100%;display:block;margin-top:10px}
.dk .dk-btn:disabled{opacity:.45;cursor:default}
.dk .dk-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.dk .dk-chips:empty{display:none}
.dk .dk-chips .dk-btn{padding:7px 12px;min-height:0;font-size:14px}
.dk .dk-lines{display:flex;flex-direction:column;gap:6px}
.dk .dk-lnrow{display:flex;gap:8px;align-items:stretch}
.dk .dk-ln{flex:1;min-width:0;text-align:right;font-family:var(--he);font-size:21px;line-height:1.3;padding:9px 12px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--fg);cursor:pointer;direction:rtl}
.dk .dk-ln.on{border-color:var(--gold);box-shadow:inset 0 0 0 1px var(--gold)}
.dk .dk-hear{flex:none;width:44px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--gold);font-size:16px;cursor:pointer}
.dk .dk-hear:disabled{opacity:.3}
.dk .dk-ptitle{margin:0 0 10px;font-size:14px;color:var(--mute)}.dk .dk-ptitle .dk-he{font-size:17px;color:var(--fg)}
.dk .dk-hero{margin:4px 0 12px;font-family:var(--he);font-size:30px;line-height:1.35;direction:rtl;text-align:right;font-weight:500}
.dk .dk-th{color:var(--gold)}.dk .dk-th.good{color:var(--good)}.dk .dk-th.bad{color:var(--bad)}.dk .dk-th.warn{color:var(--warn)}
.dk .dk-took{font-size:14px;color:var(--mute);margin:12px 0 8px}
.dk .dk-busy{margin:10px 0 0;font-size:14px;color:var(--mute);display:flex;align-items:center;gap:8px}
.dk .dk-spin{display:inline-block;width:14px;height:14px;border:2px solid var(--line);border-top-color:var(--gold);border-radius:50%;animation:dksp .8s linear infinite;flex:none}
@keyframes dksp{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion: reduce){.dk .dk-spin{animation:none}}
.dk .dk-say{font-size:17px;line-height:1.4;margin:0 0 12px}.dk .dk-say.ok{color:var(--good)}.dk .dk-say.bad{color:var(--bad)}.dk .dk-say.warn{color:var(--warn)}.dk .dk-say .dk-he{font-size:20px}
.dk .dk-words{display:flex;flex-wrap:wrap;gap:8px;direction:rtl;justify-content:flex-start}
.dk .dk-w{display:flex;flex-direction:column;align-items:center;gap:2px;min-width:68px;padding:8px 10px 6px;border-radius:12px;border:2px solid var(--line);background:transparent;color:var(--fg);cursor:pointer;font-family:var(--he);font-size:26px;line-height:1.15}
.dk .dk-w b{font-weight:500}
.dk .dk-w.ok{border-color:var(--good)}.dk .dk-w.unsure{border-color:var(--warn)}.dk .dk-w.off{border-color:var(--bad)}.dk .dk-w.sel{box-shadow:0 0 0 3px var(--gold)}
.dk .dk-w small{font-family:var(--ui);font-size:12px;color:var(--mute);direction:ltr;min-height:1em}
.dk .dk-w.off small{color:var(--bad)}.dk .dk-w.unsure small{color:var(--warn)}.dk .dk-w.ok small{color:var(--good)}
.dk .dk-notes{margin:12px 0 0;padding:0 0 0 18px;font-size:15px;line-height:1.5}.dk .dk-notes:empty{display:none}.dk .dk-notes li{margin:4px 0}.dk .dk-notes .dk-he{font-size:18px}
.dk .dk-tr{border-top:1px solid var(--line);padding:8px 0;display:flex;flex-direction:column;gap:2px;font-size:14px}
.dk .dk-tr>div{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline}.dk .dk-tr .dk-lt{font-family:var(--he);font-size:24px;color:var(--gold)}
.dk .dk-tr .dk-k{color:var(--mute);flex:none;min-width:84px}.dk .dk-tr .good{color:var(--good)}.dk .dk-tr .bad{color:var(--bad)}.dk .dk-tr .warn{color:var(--warn)}
.dk .dk-sub{border-top:1px solid var(--line);margin-top:12px;padding-top:12px}
.dk .dk-after{display:flex;gap:8px;margin-top:14px}.dk .dk-after .dk-btn{flex:1;margin-top:0}
`;
const T = {   /* every piece of text, so a site can translate or reword (Dikduk.strings) */
 lede: 'Pick a line, hear the hazzan, sing it, and see word by word how it went.', ready: 'Ready', waking: 'Waking the server…', down: 'Server not reachable',
 downMsg: 'The server did not answer. It may be waking up — try again in a minute.', s1: 'What will you sing?', pz: 'A pizmon', th: 'Tehillim',
 pzPh: 'Pizmon number, e.g. 200', thPh: 'Perek number, e.g. 23', open: 'Open', pzHint: 'You can also type a few words of the pizmon.',
 thHint: 'Perakim with Rabbi Alouf’s recording to compare with: {list}. Other perakim are checked against the nikud only.', change: 'Change',
 s2: 'Pick a line', hearHint: '▶ plays the hazzan’s recording of that line.', comparedWith: 'Compared with', main: '(main)',
 noTh: 'Rabbi Alouf’s recording of this perek is not on the server, so there is no hazzan to hear; the words and vowels are checked against the nikud.',
 noRec: 'No synced recording of this pizmon: the words are checked on their own.', comparedOne: 'Compared with the recording {rec}.',
 s3: 'Sing it', hearLine: '▶ Hear the hazzan sing it', record: '● Record', stop: '■ Stop', recNote: 'Sing or read the line, then tap Stop.',
 recording: 'Recording… tap Stop when you are done.', noTime: 'There is no hazzan recording for this line, so the check looks at your words on their own.',
 noMic: 'Recording inside this page is not allowed here: record with Voice Memos, then upload the file.', micErr: 'The microphone could not be used: ',
 recorded: 'Recorded', loaded: 'Loaded', play: '▶ Play it back', again: 'Record again', check: 'Check my singing', upload: 'Upload a recording instead',
 yourRec: 'Your recording', sending: 'sending your recording', working: 'working', ahead: ' ahead of you', failed: 'The check did not go through: ',
 lost: 'the server lost the check (it may have restarted) — check again', tooLong: 'the server took more than 7 minutes',
 s4: 'How it went', tap: 'Tap a word to hear the hazzan sing it, then you.', throatH: 'Throat letters ע and ח', you: 'you', hazzan: 'the hazzan',
 singAgain: 'Sing it again', otherLine: 'Another line', noPz: 'No pizmon {id} here.', noPerek: 'No perek {n} here.', typeSth: 'Type a number, or a few Hebrew words.',
 notFound: 'No pizmon with those words.', notLoaded: 'The words have not loaded yet — wait a moment and tap Open again.', lyricsErr: 'Could not load the words from the server.',
 allOkRef: 'Every word came through as the hazzan sings it.', allOk: 'Every word came through.', noRef: 'No hazzan recording to compare with, so only your own consonants were checked.',
 someOff: '{n} of {N} words came through. Not heard: {off}', notSure: '. Not sure: {uns}', unsureOnly: 'The words are there; not sure about {uns}.', few: 'The words are there, with a few things to hear.',
 wOff: 'not heard where it belongs', wUnsure: 'not sure it was there', notHeard: ' not heard', ayinAlef: 'the ע was said like alef', hetPlain: 'the ח was not from the throat',
 tavSamekh: 'the ת sounded like a samekh', vowHaz: 'you sang {you} where the hazzan sings {ref}', vowNik: 'you sang {you} where the nikud says {ref}',
 thThroat: 'from the throat ✓', thAlef: 'said like alef ✕', thPlain: 'not from the throat ✕', thUnsure: 'not sure', labelOk: '✓', labelUnsure: 'not sure', labelOff: 'not heard',
 lineN: 'Line {k}', pizmonN: 'Pizmon {id}', tehillimN: 'Tehillim {n}', swapped: '{a} and {b} seem swapped',
 wrongLine: 'This does not sound like this line. Check that you picked the right line, then try again.'};
const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => o[k] != null ? o[k] : m);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const he = w => `<span class="dk-he" lang="he">${esc(w)}</span>`;
const NIK = /[֑-ׇ]/g, FIN = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'};
const heL = w => String(w || '').replace(NIK, '').replace(/[ךםןףץ]/g, c => FIN[c]).replace(/[^א-ת]/g, '');
const heWords = t => String(t || '').replace(/[־\-]/g, ' ').split(/[\s,.;:!?"'״׳()\[\]{}|/\\]+/).filter(w => heL(w));
const PHR = {"md cd08 15.mp3": [[0.35, 6.9, 0], [7.4, 14, 1], [20.75, 27.7, 2], [28.1, 34.35, 3], [41.4, 50.25, 4], [50.5, 55.25, 5], [55.7, 61.35, 6], [61.85, 66.5, 7]]};
const TH_AUDIO = [1, 23, 117, 121, 130, 133, 134, 150];
let cssDone = false;
function ensureCss() { if (cssDone) return; cssDone = true; const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st); }

const HTML = `
<div class="dk-top"><p class="dk-lede"></p><span class="dk-pill wait" data-r="srv"></span></div>
<p class="dk-err" data-r="err"></p>
<section class="dk-step" data-r="s1">
 <div class="dk-sum" hidden><span class="dk-n">1</span><span class="dk-txt" data-r="s1sum"></span><button class="dk-link" type="button" data-change="s1"></button></div>
 <div class="dk-body">
  <h3><span class="dk-n">1</span><span data-t="s1"></span></h3>
  <div class="dk-seg" role="group"><button class="on" type="button" data-r="kindPz"></button><button type="button" data-r="kindTh"></button></div>
  <div class="dk-row"><input type="text" data-r="pid" style="flex:1" autocomplete="off"><button class="dk-btn gold" type="button" data-r="go"></button></div>
  <p class="dk-hint" data-r="pidHint"></p>
  <div class="dk-chips" data-r="hits"></div>
 </div>
</section>
<section class="dk-step" data-r="s2" hidden>
 <div class="dk-sum" hidden><span class="dk-n">2</span><span class="dk-txt" data-r="s2sum"></span><button class="dk-link" type="button" data-change="s2"></button></div>
 <div class="dk-body">
  <h3><span class="dk-n">2</span><span data-t="s2"></span></h3>
  <p class="dk-ptitle" data-r="ptitle"></p>
  <div class="dk-row" data-r="recs" style="margin-bottom:10px"></div>
  <div class="dk-lines" data-r="lines"></div>
  <p class="dk-hint" data-t="hearHint"></p>
 </div>
</section>
<section class="dk-step" data-r="s3" hidden>
 <div class="dk-sum" hidden><span class="dk-n">3</span><span class="dk-txt" data-t="yourRec"></span><button class="dk-link" type="button" data-change="s3" data-t="again"></button></div>
 <div class="dk-body">
  <h3><span class="dk-n">3</span><span data-t="s3"></span></h3>
  <p class="dk-hero" data-r="lineWords"></p>
  <button class="dk-btn wide" type="button" data-r="hearLine"></button>
  <button class="dk-btn wide rec" type="button" data-r="recBtn"></button>
  <p class="dk-hint" data-r="recNote"></p>
  <div data-r="takeRow" hidden>
   <p class="dk-took" data-r="took"></p>
   <div class="dk-row"><button class="dk-btn" type="button" data-r="playTake"></button><button class="dk-btn" type="button" data-r="again"></button></div>
   <button class="dk-btn wide gold" type="button" data-r="check"></button>
   <p class="dk-busy" data-r="busy" hidden></p>
  </div>
  <p class="dk-hint"><label class="dk-link" data-r="fileLab"></label><input type="file" data-r="file" accept="audio/*,video/*" hidden></p>
 </div>
</section>
<section class="dk-step" data-r="s4" hidden>
 <div class="dk-body">
  <h3><span class="dk-n">4</span><span data-t="s4"></span></h3>
  <p class="dk-say" data-r="say"></p>
  <div class="dk-words" data-r="res"></div>
  <p class="dk-hint" data-t="tap"></p>
  <ul class="dk-notes" data-r="notes"></ul>
  <div class="dk-sub" data-r="thP" hidden><h4 style="margin-top:0" data-t="throatH"></h4><div data-r="th"></div></div>
  <div class="dk-after"><button class="dk-btn gold" type="button" data-r="againLine"></button><button class="dk-btn" type="button" data-r="otherLine"></button></div>
 </div>
</section>`;

function mount(root, opts) {
 ensureCss(); opts = opts || {}; const S = Object.assign({}, T, window.Dikduk && window.Dikduk.strings || {}, opts.strings || {});
 const API = String(opts.api || '').replace(/\/$/, ''); const ARCHIVE = opts.archive || 'https://www.pizmonim.org/MP3/';
 root.classList.add('dk'); root.innerHTML = HTML;
 const $ = s => root.querySelector(`[data-r="${s}"]`); const url = p => API + p;
 root.querySelectorAll('[data-t]').forEach(e => { e.textContent = S[e.dataset.t]; });
 root.querySelector('.dk-lede').textContent = S.lede; $('srv').textContent = S.waking;
 root.querySelectorAll('[data-change]').forEach(b => { if (!b.textContent) b.textContent = S.change; });
 $('kindPz').textContent = S.pz; $('kindTh').textContent = S.th; $('go').textContent = S.open; $('hearLine').textContent = S.hearLine; $('recBtn').textContent = S.record;
 $('playTake').textContent = S.play; $('again').textContent = S.again; $('check').textContent = S.check; $('fileLab').textContent = S.upload;
 $('againLine').textContent = S.singAgain; $('otherLine').textContent = S.otherLine;
 const fid = 'dkf' + Math.random().toString(36).slice(2, 8); $('file').id = fid; $('fileLab').htmlFor = fid;
 const err = t => { $('err').textContent = t || ''; };
 let SRV = null, LY = null, P = null, REC = opts.rec || null, LINE = null, TAKE = null, RESULT = null, KIND = opts.th ? 'th' : 'pz', TAKE_URL = null;
 /* ----- steps ----- */
 const STEPS = ['s1', 's2', 's3', 's4'];
 const fold = (id, html) => { const s = $(id); s.querySelector('.dk-body').hidden = true; const sum = s.querySelector('.dk-sum'); if (sum) { sum.hidden = false; if (html != null) sum.querySelector('.dk-txt').innerHTML = html; } };
 const openStep = id => { const s = $(id); s.hidden = false; s.querySelector('.dk-body').hidden = false; const sum = s.querySelector('.dk-sum'); if (sum) sum.hidden = true; for (const k of STEPS.slice(STEPS.indexOf(id) + 1)) $(k).hidden = true; err(''); };
 const scrollTo = id => { try { $(id).scrollIntoView({behavior: 'smooth', block: 'start'}); } catch (e) {} };
 root.querySelectorAll('[data-change]').forEach(b => b.onclick = () => { const id = b.dataset.change; if (id === 's3') resetTake(); openStep(id); scrollTo(id); });
 /* ----- step 1 ----- */
 function kindHint() { const th = KIND === 'th'; $('pid').placeholder = th ? S.thPh : S.pzPh; const have = (SRV && SRV.ears && SRV.ears.tehillim_perakim) || TH_AUDIO; $('pidHint').textContent = th ? fmt(S.thHint, {list: have.join(', ')}) : S.pzHint; }
 $('kindPz').onclick = () => { KIND = 'pz'; $('kindPz').classList.add('on'); $('kindTh').classList.remove('on'); kindHint(); $('pid').focus(); };
 $('kindTh').onclick = () => { KIND = 'th'; $('kindTh').classList.add('on'); $('kindPz').classList.remove('on'); kindHint(); $('pid').focus(); };
 if (KIND === 'th') { $('kindTh').classList.add('on'); $('kindPz').classList.remove('on'); }
 async function health() { const el = $('srv'); el.className = 'dk-pill wait'; el.textContent = S.waking;
  try { const r = await fetch(url('/health'), {cache: 'no-store'}); SRV = await r.json(); el.className = 'dk-pill ok'; el.textContent = S.ready; await loadLyrics(); kindHint(); fromOpts(); }
  catch (e) { el.className = 'dk-pill bad'; el.textContent = S.down; err(S.downMsg); } }
 async function loadLyrics() { if (LY) return; try { if (opts.lyrics && typeof opts.lyrics === 'object') LY = opts.lyrics; else LY = await (await fetch(typeof opts.lyrics === 'string' ? opts.lyrics : url('/lyrics'))).json(); } catch (e) { err(S.lyricsErr); } }
 function recLines(pid, f) { const s = LY.s[pid]; const ev = (s.t && s.t[f] || '').split(';').filter(Boolean).map(x => x.split(',').map(Number)); const out = s.l.map((t, k) => ({k, text: t, t0: null, t1: null}));
  if (PHR[f]) { for (const [a, b, k] of PHR[f]) if (out[k] && out[k].t0 == null) { out[k].t0 = a; out[k].t1 = b; } return out; }
  for (let i = 0; i < ev.length; i++) { const [t, k] = ev[i]; if (k < 0 || !out[k] || out[k].t0 != null) continue; out[k].t0 = t / 10; out[k].t1 = i + 1 < ev.length ? ev[i + 1][0] / 10 : t / 10 + 8; } return out; }
 const isTh = id => /^t\d+$/.test(String(id));
 const nice = f => String(f).replace(/\.mp3$/i, '').replace(/^tehillim-0*/, 'Rabbi Alouf, perek ').replace(/^extra-/, '');
 function openP(pid) { P = null; const s = LY && LY.s[String(pid)]; if (!s) { err(isTh(pid) ? fmt(S.noPerek, {n: String(pid).slice(1)}) : fmt(S.noPz, {id: pid})); return; } P = {id: String(pid), s};
  const recs = Object.keys(s.t || {}); if (!REC || !recs.includes(REC)) REC = recs.includes(s.b) ? s.b : recs[0] || null;
  const haveTh = SRV && SRV.ears && SRV.ears.tehillim_perakim;   // the server's own list of perakim whose audio it has
  const noAudio = isTh(P.id) && SRV && SRV.ears && (haveTh ? !haveTh.includes(+P.id.slice(1)) : !SRV.ears.tehillim_audio); if (noAudio) REC = null;
  const label = isTh(P.id) ? fmt(S.tehillimN, {n: P.id.slice(1)}) : fmt(S.pizmonN, {id: P.id});
  fold('s1', esc(label)); $('ptitle').innerHTML = esc(label) + ' · ' + he(s.l[0]);
  if (!REC) $('recs').innerHTML = '<span class="dk-hint" style="margin:0">' + esc(isTh(P.id) ? S.noTh : S.noRec) + '</span>';
  else if (recs.length === 1) $('recs').innerHTML = '<span class="dk-hint" style="margin:0">' + esc(fmt(S.comparedOne, {rec: nice(REC)})) + '</span>';
  else { $('recs').innerHTML = '<label class="dk-hint" style="margin:0;display:flex;align-items:center;gap:8px;flex:1">' + esc(S.comparedWith) + ' <select style="flex:1">' + recs.map(f => `<option value="${esc(f)}"${f === REC ? ' selected' : ''}>${esc(nice(f))}${f === s.b ? ' ' + esc(S.main) : ''}</option>`).join('') + '</select></label>';
   $('recs').querySelector('select').onchange = e => { REC = e.target.value; openP(pid); }; }
  const L = recLines(P.id, REC || recs[0] || null); if (noAudio) L.forEach(l => { l.t0 = null; l.t1 = null; });
  $('lines').innerHTML = L.map(l => `<div class="dk-lnrow"><button class="dk-hear" type="button" data-hear="${l.k}" ${l.t0 == null ? 'disabled' : ''}>▶</button><button class="dk-ln" type="button" data-k="${l.k}" lang="he">${esc(l.text)}</button></div>`).join('');
  $('lines').querySelectorAll('.dk-ln').forEach(b => b.onclick = () => pickLine(L[+b.dataset.k]));
  $('lines').querySelectorAll('[data-hear]').forEach(b => b.onclick = () => { const l = L[+b.dataset.hear]; playHim(l.t0, l.t1); });
  openStep('s2'); }
 $('go').onclick = async () => { await loadLyrics(); if (!LY) { err(S.notLoaded); return; } const v = $('pid').value.trim(); $('hits').innerHTML = ''; if (!v) return; REC = null;
  if (/^t\s*\d+$/i.test(v)) { openP('t' + v.replace(/\D/g, '')); scrollTo('s2'); return; }
  if (/^\d+$/.test(v)) { openP(KIND === 'th' ? 't' + v : v); scrollTo('s2'); return; }
  const Q = heWords(v).map(heL); if (!Q.length) { err(S.typeSth); return; }
  const hits = []; for (const id in LY.s) { if (isTh(id)) continue; const W = heWords(LY.s[id].l.join(' ')).map(heL); let h = 0; for (const w of Q) if (W.some(t => t === w || (w.length >= 3 && t.includes(w)))) h++; if (h === Q.length) hits.push(id); if (hits.length > 12) break; }
  $('hits').innerHTML = hits.map(id => `<button class="dk-btn" type="button" data-id="${id}">${id} · ${he(LY.s[id].l[0].split(' ').slice(0, 4).join(' '))}</button>`).join('') || '<span class="dk-hint" style="margin:0">' + esc(S.notFound) + '</span>';
  $('hits').querySelectorAll('button').forEach(b => b.onclick = () => { $('pid').value = b.dataset.id; openP(b.dataset.id); scrollTo('s2'); }); };
 $('pid').addEventListener('keydown', e => { if (e.key === 'Enter') $('go').click(); });
 function fromOpts() { const pz = opts.pz, th = opts.th; if (!pz && !th) return; const id = th ? 't' + String(th).replace(/\D/g, '') : String(pz); $('pid').value = th ? String(th).replace(/\D/g, '') : id; openP(id);
  const k = parseInt(opts.line || '', 10); if (k >= 1) { const b = $('lines').querySelector(`.dk-ln[data-k="${k - 1}"]`); if (b) b.click(); } }
 /* ----- step 2 → 3 ----- */
 const PREF = new Set();
 function prefetchRef(l) { if (!REC || l.t0 == null) return; const k = REC + '|' + l.t0 + '|' + l.t1 + '|' + l.text; if (PREF.has(k)) return; PREF.add(k); fetch(url('/ref?' + new URLSearchParams({f: REC, words: l.text, t0: l.t0, t1: l.t1})), {cache: 'no-store'}).catch(() => PREF.delete(k)); }
 const hiTh = (w, cls) => esc(w).replace(/[עח]/g, c => `<span class="dk-th${cls ? ' ' + cls(c) : ''}">${c}</span>`);
 function pickLine(l) { LINE = l; TAKE = null; RESULT = null; prefetchRef(l); $('lines').querySelectorAll('.dk-ln').forEach(b => b.classList.toggle('on', +b.dataset.k === l.k));
  fold('s2', esc(fmt(S.lineN, {k: l.k + 1})) + ' · ' + he(l.text)); $('lineWords').innerHTML = hiTh(l.text); $('hearLine').disabled = l.t0 == null; $('takeRow').hidden = true; if (canRec) $('recBtn').hidden = false;
  $('recNote').textContent = l.t0 == null ? S.noTime : S.recNote; openStep('s3'); scrollTo('s3'); }
 /* ----- the hazzan ----- */
 let HIM = null;
 const himSrc = f => /^(tehillim-|extra-)/.test(f) ? url('/tehillim/audio/' + encodeURIComponent(f)) : ARCHIVE + encodeURIComponent(f);
 function playHim(t0, t1) { if (!REC || t0 == null) return; const src = himSrc(REC); if (!HIM || HIM.dataset.src !== src) { HIM = new Audio(src); HIM.dataset.src = src; HIM.preload = 'auto'; }
  HIM.pause(); const stop = () => { if (HIM.currentTime >= t1 - .02) { HIM.pause(); HIM.removeEventListener('timeupdate', stop); } }; HIM.currentTime = Math.max(0, t0); HIM.addEventListener('timeupdate', stop); HIM.play().catch(() => {}); }
 $('hearLine').onclick = () => LINE && playHim(LINE.t0, LINE.t1);
 /* ----- the take ----- */
 let MR = null, CH = [], T0 = 0, TK = null;
 const canRec = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
 if (!canRec) { $('recBtn').hidden = true; $('recNote').textContent = S.noMic; }
 $('recBtn').onclick = async () => { if (MR && MR.state === 'recording') { MR.stop(); return; }
  try { const st = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
   const mt = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', ''].find(t => !t || MediaRecorder.isTypeSupported(t)); MR = new MediaRecorder(st, mt ? {mimeType: mt} : undefined); CH = []; MR.ondataavailable = e => { if (e.data.size) CH.push(e.data); };
   MR.onstop = () => { st.getTracks().forEach(t => t.stop()); clearInterval(TK); $('recBtn').textContent = S.record; setTake(new Blob(CH, {type: MR.mimeType || 'audio/mp4'}), 'rec', (Date.now() - T0) / 1000); };
   MR.start(250); T0 = Date.now(); $('takeRow').hidden = true; $('recBtn').textContent = S.stop + ' · 0.0 s'; $('recNote').textContent = S.recording;
   TK = setInterval(() => { $('recBtn').textContent = S.stop + ' · ' + ((Date.now() - T0) / 1000).toFixed(1) + ' s'; if (Date.now() - T0 > 45000) MR.stop(); }, 200); }
  catch (e) { err(S.micErr + e.message); } };
 $('file').onchange = e => { const f = e.target.files[0]; if (f) setTake(f, f.name, null); e.target.value = ''; };
 function resetTake() { TAKE = null; $('takeRow').hidden = true; $('recNote').textContent = ''; if (canRec) $('recBtn').hidden = false; }
 $('again').onclick = () => { resetTake(); if (canRec) $('recBtn').click(); };
 function setTake(blob, name, secs) { TAKE = {blob, name}; if (TAKE_URL) URL.revokeObjectURL(TAKE_URL); TAKE_URL = URL.createObjectURL(blob); $('takeRow').hidden = false; $('recBtn').hidden = true; err('');
  $('took').textContent = name === 'rec' ? S.recorded + ' · ' + secs.toFixed(1) + ' s' : S.loaded + ' ' + name; $('recNote').textContent = ''; }
 let YOU = null;
 function playYou(t0, t1) { if (!TAKE_URL) return; if (!YOU || YOU.dataset.src !== TAKE_URL) { YOU = new Audio(TAKE_URL); YOU.dataset.src = TAKE_URL; }
  YOU.pause(); const stop = () => { if (t1 != null && YOU.currentTime >= t1 - .02) { YOU.pause(); YOU.removeEventListener('timeupdate', stop); } }; YOU.currentTime = t0 || 0; if (t1 != null) YOU.addEventListener('timeupdate', stop); YOU.play().catch(() => {}); }
 $('playTake').onclick = () => playYou(0, null);
 /* ----- the check: queued on the server, polled ----- */
 const busyText = t => { $('busy').innerHTML = '<span class="dk-spin"></span><span>' + esc(t) + '…</span>'; };
 async function waitJob(id) { const t0 = Date.now(); let misses = 0;
  for (;;) { await new Promise(s => setTimeout(s, 1500)); let st;
   try { const r = await fetch(url('/job/' + id), {cache: 'no-store'}); st = await r.json(); if (r.status === 404) throw new Error(st.err || S.lost); } catch (e) { if (++misses > 8) throw e; continue; }
   misses = 0; busyText((st.stage || S.working) + ' · ' + Math.round((Date.now() - t0) / 1000) + ' s' + (st.queued ? ' · ' + st.queued + S.ahead : ''));
   if (st.state === 'done') return st.result; if (st.state === 'error') throw new Error(st.err || 'error'); if (Date.now() - t0 > 420000) throw new Error(S.tooLong); } }
 $('check').onclick = async () => { if (!TAKE || !LINE) return; busyText(S.sending); $('busy').hidden = false; $('check').disabled = true; err('');
  try { const q = new URLSearchParams({words: LINE.text, job: 1}); if (REC && LINE.t0 != null) { q.set('ref', REC); q.set('t0', LINE.t0); q.set('t1', LINE.t1); } if (P && P.s.ln && P.s.ln[LINE.k]) q.set('nikud', P.s.ln[LINE.k]);
   const r = await fetch(url('/check?' + q), {method: 'POST', body: TAKE.blob, headers: {'content-type': TAKE.blob.type || 'application/octet-stream'}}); let j = await r.json(); if (!r.ok || j.err) throw new Error(j.err || ('server said ' + r.status));
   if (j.job) j = await waitJob(j.job); RESULT = j; render(j); if (typeof opts.onResult === 'function') { try { opts.onResult(j, {pid: P.id, line: LINE.k, rec: REC}); } catch (e) {} } }
  catch (e) { err(S.failed + e.message); }
  $('busy').hidden = true; $('check').disabled = false; };
 /* ----- the verdicts (the same rule as the Space's page) ----- */
 let CLEAN = false;
 function markOf(y, f) { const n = y && y.n || 0, sk = y && y.skel != null ? y.skel : null, ft = f && f.fit != null ? f.fit : null; if (!n || sk == null) return ''; const kp = y && y.kept != null ? y.kept : null, pw = y && y.pw != null ? y.pw : null, hs = y && y.hskel != null ? y.hskel : null;
  const sure = CLEAN && kp != null && kp >= .75 && hs != null && hs >= .6 && (pw == null || pw < .8);
  if (n >= 2) { if (sk < .2 && (ft == null || ft < .15)) { if (ft == null && CLEAN && !(kp != null && kp < .75)) return 'unsure'; return 'off'; } if (CLEAN && pw != null && pw >= .95) return 'off'; if (sure) return 'ok'; if (sk < .4 || (ft != null && ft < .2) || (kp != null && kp < .5) || (pw != null && pw >= .8)) return 'unsure'; return 'ok'; } return sk < .2 && !sure ? 'unsure' : 'ok'; }
 /* whole-line evidence on a clean take (server: order.py); thresholds from exam_alouf.py — kept in step with index.html */
 const RULE = {drop: 10, margin: 4, swap: 8, gap: 0.6};
 function marksOf(TW, F, gap) { const marks = TW.map((t, i) => markOf(t, F && F[i])); const why = TW.map(() => null); let lineWrong = false;
  if (CLEAN) { const ds = TW.map(t => t.drop == null ? -1e9 : t.drop); const top = ds.indexOf(Math.max(...ds)); const second = Math.max(...ds.filter((d, i) => i !== top), -1e9);
   if (top >= 0 && (TW[top].n || 0) >= 2 && ds[top] >= RULE.drop && ds[top] - second >= RULE.margin) { marks[top] = 'off'; why[top] = 'dropped'; }
   const sw = TW.slice(0, -1).map(t => t.swap == null ? -1e9 : t.swap); if (sw.length) { const j = sw.indexOf(Math.max(...sw)), na = TW[j].n || 0, nb = TW[j + 1].n || 0; if (sw[j] >= RULE.swap && Math.max(na, nb) >= 2 && Math.min(na, nb) >= 1) { marks[j] = 'off'; marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'; } }
   if (gap != null && gap >= RULE.gap) { lineWrong = true; for (let i = 0; i < marks.length; i++) if (marks[i] === 'ok') marks[i] = 'unsure'; } }
  return {marks, why, lineWrong}; }
 const VCLS = {throat: 'good', plain: 'bad', unsure: 'warn'};
 const thLead = t => !t || !t.v ? '–' : t.v === 'throat' ? S.thThroat : t.v === 'plain' ? (t.c === 'ע' ? S.thAlef : S.thPlain) : S.thUnsure;
 function render(j) { const W = j.words, TW = j.take.words, RW = j.ref ? j.ref.words : null, F = j.fit || null;
  const hs = TW.filter(t => (t.n || 0) >= 2 && t.hskel != null).map(t => t.hskel).sort((a, b) => a - b); CLEAN = hs.length > 0 && hs[Math.floor(hs.length / 2)] >= .7;
  const {marks, why, lineWrong} = marksOf(TW, F, j.take.gap); const LABEL = {ok: S.labelOk, unsure: S.labelUnsure, off: S.labelOff, '': ''};
  $('res').innerHTML = W.map((w, i) => { const t = TW[i]; let n = 0; const ths = (t.throat || []); const cls = () => { const th = ths[n++]; if (!th || marks[i] === 'off') return ''; if (th.v === 'plain') { const r = RW && RW[i] && (RW[i].throat || []).find(x => x.k === th.k); if (r && r.v === 'plain') return ''; } return VCLS[th.v] || ''; };
   return `<button class="dk-w ${marks[i]}" type="button" data-i="${i}" lang="he"><b>${hiTh(w, cls)}</b><small>${LABEL[marks[i]]}</small></button>`; }).join('');
  $('res').querySelectorAll('.dk-w').forEach(b => b.onclick = () => { const i = +b.dataset.i; $('res').querySelectorAll('.dk-w').forEach(x => x.classList.toggle('sel', x === b)); const r = RW && RW[i], f = F && F[i], t = TW[i];
   const mine = f && f.t0 != null ? [f.t0, f.t1] : t && t.t0 != null ? [t.t0, t.t1] : null;
   if (r && LINE.t0 != null) { playHim(LINE.t0 + r.t0 - .1, LINE.t0 + r.t1 + .1); const wait = (r.t1 - r.t0 + .4) * 1000; setTimeout(() => { if (mine) playYou(Math.max(0, mine[0] - .15), mine[1] + .15); }, wait + 150); }
   else if (mine) playYou(Math.max(0, mine[0] - .15), mine[1] + .15); });
  const VN = j.vowel_names || {}; const vname = k => esc((VN[k] || k).split(' ')[0]); const lines = [];
  W.forEach((w, i) => { const t = TW[i]; const parts = [];
   if (why[i] === 'swapped') { if (i + 1 < W.length && why[i + 1] === 'swapped' && TW[i].swap != null && TW[i].swap >= RULE.swap) parts.push(fmt(S.swapped, {a: he(w), b: he(W[i + 1])})); }
   else if (marks[i] === 'off') parts.push(S.wOff); else if (marks[i] === 'unsure') parts.push(S.wUnsure);
   if (marks[i] !== 'ok' && t.miss && t.miss.length && t.miss.length < (t.n || 9)) parts.push(he(t.miss.join(' ')) + S.notHeard);
   if (marks[i] !== 'off') (t.throat || []).forEach(th => { if (th.v !== 'plain') return; const r = RW && RW[i] && (RW[i].throat || []).find(x => x.k === th.k); if (r && r.v === 'plain') return; parts.push(th.c === 'ע' ? S.ayinAlef : S.hetPlain); });
   (t.notes || []).forEach(nn => { if (nn.say === 'sav') parts.push(S.tavSamekh); });
   const vd = marks[i] === 'off' ? [] : ((j.vowels && j.vowels[i]) || []), vn = marks[i] === 'off' ? [] : ((j.vowels_nikud && j.vowels_nikud[i]) || []);
   vd.forEach(d => parts.push(fmt(S.vowHaz, {you: vname(d.you), ref: vname(d.ref)}))); vn.forEach(d => { if (!vd.some(x => x.k === d.k)) parts.push(fmt(S.vowNik, {you: vname(d.you), ref: vname(d.ref)})); });
   if (parts.length) lines.push(`<li>${he(w)}: ${parts.join('; ')}.</li>`); });
  const offW = W.filter((w, i) => marks[i] === 'off'), unsW = W.filter((w, i) => marks[i] === 'unsure'), say = $('say');
  if (lineWrong) { say.className = 'dk-say bad'; say.textContent = S.wrongLine; }
  else if (!F && j.ref_err && !/Tehillim/.test(j.ref_err)) { say.className = 'dk-say warn'; say.textContent = S.noRef; }
  else if (!lines.length) { say.className = 'dk-say ok'; say.textContent = F ? S.allOkRef : S.allOk; }
  else if (offW.length) { say.className = 'dk-say bad'; say.innerHTML = fmt(S.someOff, {n: W.length - offW.length, N: W.length, off: offW.map(he).join(', ')}) + (unsW.length ? fmt(S.notSure, {uns: unsW.map(he).join(', ')}) : '') + '.'; }
  else if (unsW.length) { say.className = 'dk-say warn'; say.innerHTML = fmt(S.unsureOnly, {uns: unsW.map(he).join(', ')}); }
  else { say.className = 'dk-say warn'; say.textContent = S.few; }
  $('notes').innerHTML = lines.join('');
  const rows = []; TW.forEach((t, i) => { if (marks[i] === 'off') return; (t.throat || []).forEach(th => { const r = RW && RW[i] && (RW[i].throat || []).find(x => x.k === th.k); rows.push({w: W[i], c: th.c, you: th, him: r}); }); });
  if (rows.length) { $('th').innerHTML = rows.map(x => `<div class="dk-tr"><div><span class="dk-lt">${esc(x.c)}</span><span>${he(x.w)}</span></div><div><span class="dk-k">${esc(S.you)}</span><span class="${VCLS[x.you.v] || ''}">${esc(thLead(x.you))}</span></div><div><span class="dk-k">${esc(S.hazzan)}</span><span>${esc(thLead(x.him))}</span></div></div>`).join(''); $('thP').hidden = false; } else $('thP').hidden = true;
  fold('s3'); $('s4').hidden = false; $('s4').querySelector('.dk-body').hidden = false; scrollTo('s4'); }
 $('againLine').onclick = () => { resetTake(); openStep('s3'); scrollTo('s3'); };
 $('otherLine').onclick = () => { openStep('s2'); scrollTo('s2'); };
 health();
 return {open: id => { LY ? openP(id) : null; }, get result() { return RESULT; }};
}
window.Dikduk = Object.assign(window.Dikduk || {}, {mount, strings: (window.Dikduk && window.Dikduk.strings) || {}, version: '4.3'});
function auto() { document.querySelectorAll('[data-dikduk]').forEach(el => { if (el.dataset.dkMounted) return; el.dataset.dkMounted = '1'; mount(el, {api: el.dataset.api, pz: el.dataset.pz, th: el.dataset.th, line: el.dataset.line, rec: el.dataset.rec, archive: el.dataset.archive}); }); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto); else auto();
})();
