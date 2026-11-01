/* Dikduk checker — drop-in for a site page.
   <div id="dikduk"></div>
   <script src="embed.js"></script>
   <script>Dikduk.mount(document.getElementById('dikduk'), {api:'https://davidsitt-pizmonim-dikduk.hf.space', pz:'200', line:3});</script>
   or simply <div data-dikduk data-api="https://…hf.space" data-pz="200" data-line="3"></div> and the script mounts it.
   Options: api (the checker server — or several, an array or a space-separated string: the first one is used when its
   /health answers within 1.5 s (another one only after that, or once the first has failed), so a fast home server can come first and the Space second as the fallback; if a check cannot reach
   the chosen one, the others are asked once more), pz | th (pizmon id | Tehillim perek), line (1-based), rec (hazzan recording file),
   lyrics (the site's lyrics object or a URL — saves a fetch), archive (base URL of the archive mp3s), follow (true: words light up while recording, even on a slow server; false: never; default: on a fast server),
   notes ('words' | 'letters' | 'all': which notes show at first), strict (1/true/on/yes: start with the
   strict check on — data-strict="1"; the person can switch it under the result, and their own last choice wins over this), letters (where the "practice ע ›" links
   go: a URL — default the server's /letters page — or false for no links; data-letters), onResult(result, {pid, line, rec, strict}).
   Styling: everything is under .dk; colours and fonts are CSS variables on the container (--dk-bg, --dk-panel, --dk-line,
   --dk-fg, --dk-mute, --dk-accent, --dk-good, --dk-warn, --dk-bad, --dk-ink, --dk-he, --dk-ui); the site's own fonts are
   inherited unless --dk-he / --dk-ui are set. Browser storage (this browser only): the strict and notes switches (dk.strict, dk.notes),
   the voice card (dk.vc), the tries per line (dk.hist.*) and the questions sent to a hazzan (dk.reviews: id + token).
   v5 also adds: hide a note and, with a yes, send the take (POST /feedback); "Ask a hazzan" (POST /review, answered on
   the server's /hazzan page; both offered only by a server whose storage is durable); "The hazzan, then you"; the voice card (Tehillim 23:1-2 read once: /check with vc=…). The same checker as the Space's /try page. */
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
.dk .dk-sv{color:var(--warn);text-decoration:underline dotted;text-underline-offset:5px}
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
.dk .dk-prac{color:var(--gold);font-size:14px;white-space:nowrap;text-decoration:none;border-bottom:1px solid currentColor}
.dk .dk-fw{transition:color .25s}.dk .dk-fw.on{color:var(--gold)}
.dk .dk-opts{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;font-size:14px;color:var(--mute);margin:-6px 0 12px}.dk .dk-opts .dk-strict{margin:0}
.dk .dk-x{border:0;background:transparent;color:var(--mute);font-size:18px;line-height:1;padding:0 4px;margin-left:6px;cursor:pointer;vertical-align:middle}.dk .dk-x:hover{color:var(--bad)}
.dk .dk-share,.dk .dk-ask,.dk .dk-qs{border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-top:12px}.dk .dk-share p,.dk .dk-qs p{margin:0 0 8px}
.dk .dk-ask{border:0;padding:0}.dk textarea{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 12px;width:100%;box-sizing:border-box;margin:8px 0}
.dk .dk-ask input[type=text]{width:100%;box-sizing:border-box;margin:0 0 8px}.dk .dk-qs h4{margin:0 0 6px}.dk .dk-q{border-top:1px solid var(--line);padding:8px 0 4px}.dk .dk-q:first-of-type{border-top:0}
.dk .dk-q .dk-ans{white-space:pre-wrap;margin:6px 0}.dk .dk-new{color:var(--gold);font-weight:700}
.dk .dk-strict{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--mute,inherit);margin:-4px 0 12px;cursor:pointer}.dk .dk-strict input{width:18px;height:18px;accent-color:var(--gold);margin:0}
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
 wrongLine: 'This does not sound like this line. Check that you picked the right line, then try again.',
 cantHear: 'I could not make out the words of this line in the recording. Check that it is the right line, then try again a little closer to the phone, without music in the background.',
 strictL: 'Strict check: only what is clearly right counts', labelUnclear: 'not clear', wUnclear: 'not clearly right',
 someOffStrict: '{n} of {N} words came through clearly. Not clearly right: {off}', ayinUnclear: 'the ע was not clearly from the throat', hetUnclear: 'the ח was not clearly from the throat', thUnclear: 'not clearly ✕',
 strictUnclear: 'This take is not clear enough for a strict check. Record again in a quiet room, phone close to your mouth — or turn the strict check off.',
 practice: 'practice {c} ›', shvaNa: 'say a short “e” after the {c} (shva na)', shvaNah: 'no vowel after the {c} — its shva is silent (shva nah)',
 shvaWhy: {start: 'a shva at the start of a word is said', second: 'the second of two shvas in a row is said', twin: 'a shva under the first of two identical letters is said',
  dagesh: 'a shva under a doubled letter (dagesh) is said', short: 'after a short vowel the shva closes the syllable', first: 'the first of two shvas in a row is silent',
  final: 'a shva at the end of a word is silent', hazzan: 'listen to the hazzan here'},
 notesL: 'Notes on:', notesLetters: 'letters ע ח ת', notesVowels: 'vowels & shva', histL: 'Your tries on this line: ', bothLine: '▶ The hazzan, then you',
 dismiss: 'Not my mistake — hide this note', shareQ: 'Help fix the checker: send this recording, with the note you hid?', shareYes: 'Send it', shareNo: 'No thanks',
 shareDone: 'Sent — thank you. It goes into the next round of training.', shareFail: 'Could not send it: ',
 askBtn: 'Ask a hazzan to listen', askNote: 'What should he listen for? (optional)', askContact: 'Your name or email, so he can reach you (optional)', askSend: 'Send', askCancel: 'Cancel',
 askSent: 'Sent. His answer will show here, at the top of the checker.', askFail: 'Could not send it: ', askMine: 'Your questions to a hazzan', askWaiting: 'waiting for an answer',
 askAnswered: 'answered', askGone: 'no longer on the server', askPlay: '▶ your recording',
 vcLink: 'Tune the checker to your voice (1 minute)', vcOn: 'tuned to your voice ✓', vcForget: 'forget it', vcTitle: 'Tune to your voice',
 vcIntro: 'Read these two pesukim carefully, at your normal pace, then tap Stop. The checker learns which vowels it mishears in your voice and stops flagging those — never a real mistake, like “a” for a kamatz katan.',
 vcBusy: 'listening', vcDone: 'Tuned. For your voice the checker will no longer flag: {pairs}.', vcNothing: 'Done: the checker hears your vowels well — there was nothing to tune.',
 vcUnclear: 'Not clear enough to tune from. Try again a little closer to the phone, in a quiet room.', vcNoText: 'Tuning needs Tehillim 23 from the server.', vcClose: 'Close',
 vcPair: {'U>O': '“oo” heard as “oh”', 'O>U': '“oh” heard as “oo”', 'E>I': '“eh” heard as “ee”', 'I>E': '“ee” heard as “eh”'},
 noSpeech: 'I did not hear any singing in this recording. Check that the microphone picked you up (hold the phone closer), then record again.'};
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
<div class="dk-qs" data-r="qs" hidden></div>
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
  <p class="dk-hint" data-r="vcRow"><button class="dk-link" type="button" data-r="vcOpen"></button><span data-r="vcState"></span></p>
 </div>
</section>
<section class="dk-step" data-r="s4" hidden>
 <div class="dk-body">
  <h3><span class="dk-n">4</span><span data-t="s4"></span></h3>
  <p class="dk-say" data-r="say"></p>
  <label class="dk-strict"><input type="checkbox" data-r="strict"><span data-t="strictL"></span></label>
  <div class="dk-opts"><span data-t="notesL"></span><label class="dk-strict"><input type="checkbox" data-r="nLet"><span data-t="notesLetters"></span></label><label class="dk-strict"><input type="checkbox" data-r="nVow"><span data-t="notesVowels"></span></label></div>
  <div class="dk-words" data-r="res"></div>
  <p class="dk-hint" data-t="tap"></p>
  <button class="dk-btn" type="button" data-r="bothLine" hidden></button>
  <ul class="dk-notes" data-r="notes"></ul>
  <div class="dk-share" data-r="share" hidden><p data-r="shareP"></p><div class="dk-row" data-r="shareRow"><button class="dk-btn gold" type="button" data-r="shareYes"></button><button class="dk-btn" type="button" data-r="shareNo"></button></div></div>
  <p class="dk-hint" data-r="hist"></p>
  <div class="dk-sub" data-r="thP" hidden><h4 style="margin-top:0" data-t="throatH"></h4><div data-r="th"></div></div>
  <div class="dk-ask"><button class="dk-btn wide" type="button" data-r="askBtn"></button>
   <div data-r="askForm" hidden><textarea data-r="askNote" rows="2"></textarea><input type="text" data-r="askContact" autocomplete="off"><div class="dk-row"><button class="dk-btn gold" type="button" data-r="askSend"></button><button class="dk-btn" type="button" data-r="askCancel"></button></div></div>
   <p class="dk-hint" data-r="askMsg"></p></div>
  <div class="dk-after"><button class="dk-btn gold" type="button" data-r="againLine"></button><button class="dk-btn" type="button" data-r="otherLine"></button></div>
 </div>
</section>
<section class="dk-step" data-r="vc" hidden>
 <div class="dk-body">
  <h3><span data-t="vcTitle"></span></h3>
  <p class="dk-hint" data-t="vcIntro"></p>
  <p class="dk-hero" data-r="vcText" lang="he"></p>
  <button class="dk-btn wide rec" type="button" data-r="vcRec"></button>
  <p class="dk-busy" data-r="vcBusy" hidden></p>
  <p class="dk-say" data-r="vcSay"></p>
  <button class="dk-btn" type="button" data-r="vcClose"></button>
 </div>
</section>`;

function mount(root, opts) {
 ensureCss(); opts = opts || {}; const S = Object.assign({}, T, window.Dikduk && window.Dikduk.strings || {}, opts.strings || {});
 const APIS = [].concat(opts.api || []).join(' ').split(/[\s,]+/).filter(Boolean).map(a => a.replace(/\/$/, '')); let API = APIS[0] || ''; const ARCHIVE = opts.archive || 'https://www.pizmonim.org/MP3/';
 root.classList.add('dk'); root.innerHTML = HTML;
 const $ = s => root.querySelector(`[data-r="${s}"]`); const url = p => API + p;
 const practice = (c, want) => { if (opts.letters === false || opts.letters === 'false') return ''; const base = (typeof opts.letters === 'string' && opts.letters) ? opts.letters : url('/letters'); const q = new URLSearchParams({c}); if (want) q.set('want', want); return ` <a class="dk-prac" href="${esc(base + (base.includes('?') ? '&' : '?') + q)}" target="_blank" rel="noopener">${esc(fmt(S.practice, {c}))}</a>`; };
 /* several servers: the first (the home Mac) when its /health says ok; another one only from 1.5 s after the start, or once the first
    has failed — so a quick Space never beats a working Mac; a dead tunnel fails fast, a sleeping Space answers late */
 function pickApi() { if (APIS.length <= 1) return fetch(url('/health'), {cache: 'no-store'}).then(r => r.json());
  return new Promise((res, rej) => { let left = APIS.length, done = false, wake; const t0 = Date.now(), firstOut = new Promise(s => { wake = s; });
   APIS.forEach(async (a, i) => { try { const r = await fetch(a + '/health', {cache: 'no-store'}); if (!r.ok) throw new Error(String(r.status)); const j = await r.json(); if (!j || !j.ok) throw new Error('not ok');
     if (i > 0) await Promise.race([firstOut, new Promise(s => setTimeout(s, t0 + 1500 - Date.now()))]); if (!done) { done = true; API = a; res(j); } }
   catch (e) { if (i === 0) wake(); if (--left === 0 && !done) rej(e); } }); }); }
 root.querySelectorAll('[data-t]').forEach(e => { e.textContent = S[e.dataset.t]; });
 root.querySelector('.dk-lede').textContent = S.lede; $('srv').textContent = S.waking;
 root.querySelectorAll('[data-change]').forEach(b => { if (!b.textContent) b.textContent = S.change; });
 $('kindPz').textContent = S.pz; $('kindTh').textContent = S.th; $('go').textContent = S.open; $('hearLine').textContent = S.hearLine; $('recBtn').textContent = S.record;
 $('playTake').textContent = S.play; $('again').textContent = S.again; $('check').textContent = S.check; $('fileLab').textContent = S.upload;
 $('againLine').textContent = S.singAgain; $('otherLine').textContent = S.otherLine;
 $('bothLine').textContent = S.bothLine; $('shareYes').textContent = S.shareYes; $('shareNo').textContent = S.shareNo; $('askBtn').textContent = S.askBtn; $('askSend').textContent = S.askSend; $('askCancel').textContent = S.askCancel;
 $('askNote').placeholder = S.askNote; $('askContact').placeholder = S.askContact; $('vcOpen').textContent = S.vcLink; $('vcRec').textContent = S.record; $('vcClose').textContent = S.vcClose;
 const fid = 'dkf' + Math.random().toString(36).slice(2, 8); $('file').id = fid; $('fileLab').htmlFor = fid;
 const err = t => { $('err').textContent = t || ''; };
 /* the person's own last choice (dk.strict '1'/'0') wins over the site's default (strict: 1/true/on/yes) */
 let STRICT = (() => { let st = null; try { st = localStorage.getItem('dk.strict'); } catch (e) {} if (st === '1' || st === '0') return st === '1';
  return opts.strict === true || /^(1|true|on|yes)$/i.test(String(opts.strict == null ? '' : opts.strict).trim()); })();
 let SRV = null, LY = null, P = null, REC = opts.rec || null, LINE = null, TAKE = null, RESULT = null, KIND = opts.th ? 'th' : 'pz', TAKE_URL = null;
 /* v5 — what to check (Tarteel's tashkeel switch): letter notes, vowel & shva notes; opts.notes = 'words' | 'letters' | 'all' */
 const ls = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } };
 const NOTES = (() => { const o = String(opts.notes || '').toLowerCase(); if (o === 'words') return {l: false, v: false}; if (o === 'letters') return {l: true, v: false}; if (o === 'all') return {l: true, v: true};
  const st = ls('dk.notes'); return st ? {l: st.includes('l'), v: st.includes('v')} : {l: true, v: true}; })();
 /* v5 — the voice card (Kriah Listener): vowel confusions the ear makes on this voice, learned once from Tehillim 23:1-2 */
 let VC = (() => { try { return JSON.parse(ls('dk.vc') || 'null'); } catch (e) { return null; } })();
 /* v5 — notes the person hid (Tarteel: remove a wrong flag), and whether they already sent this take */
 let HIDDEN = new Set(), SHARED = false, LAST = {ok: 0, n: 0, marks: [], notes: []};
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
  try { SRV = await pickApi(); el.className = 'dk-pill ok'; el.textContent = S.ready; await loadLyrics(); kindHint(); fromOpts(); }
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
 function prefetchRef(l) { if (!REC || l.t0 == null) return; const nk = P && P.s.ln && P.s.ln[l.k]; const k = REC + '|' + l.t0 + '|' + l.t1 + '|' + l.text + '|' + (nk || ''); if (PREF.has(k)) return; PREF.add(k); const q = new URLSearchParams({f: REC, words: l.text, t0: l.t0, t1: l.t1}); if (nk) q.set('nikud', nk); fetch(url('/ref?' + q), {cache: 'no-store'}).then(r => { if (!r.ok) PREF.delete(k); }).catch(() => PREF.delete(k)); }   /* refused (busy): a later pick tries again */
 const hiTh = (w, cls) => esc(w).replace(/[עח]/g, c => `<span class="dk-th${cls ? ' ' + cls(c) : ''}">${c}</span>`);
 /* the throat letters as above, and the letters a shva note is about (sv: their letter indices) underlined */
 const hiW = (w, cls, sv) => { if (!sv || !sv.size) return hiTh(w, cls); let k = -1; return [...String(w)].map(c => { if (/[א-ת]/.test(c)) k++; if (/[א-ת]/.test(c) && sv.has(k)) return `<span class="dk-sv">${esc(c)}</span>`; return /[עח]/.test(c) ? `<span class="dk-th${cls ? ' ' + cls(c) : ''}">${c}</span>` : esc(c); }).join(''); };
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
 /* RBUSY: from the tap until onstop, so a second tap while the mic opens cannot start a second recorder; each take has its own
    chunks (ch) and stream (st) — CH only points at the current take's chunks, for the follow-along */
 let MR = null, CH = [], T0 = 0, TK = null, RBUSY = false;
 const canRec = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
 if (!canRec) { $('recBtn').hidden = true; $('recNote').textContent = S.noMic; }
 $('recBtn').onclick = async () => { if (MR && MR.state === 'recording') { MR.stop(); return; } if (RBUSY) return; RBUSY = true; let st = null;
  try { st = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
   const mt = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', ''].find(t => !t || MediaRecorder.isTypeSupported(t)), ch = []; const mr = new MediaRecorder(st, mt ? {mimeType: mt} : undefined); MR = mr; CH = ch; mr.ondataavailable = e => { if (e.data.size) ch.push(e.data); };
   mr.onstop = () => { RBUSY = false; st.getTracks().forEach(t => t.stop()); clearInterval(TK); followStop(); $('recBtn').textContent = S.record; setTake(new Blob(ch, {type: mr.mimeType || 'audio/mp4'}), 'rec', (Date.now() - T0) / 1000); };
   mr.start(250); T0 = Date.now(); $('takeRow').hidden = true; $('recBtn').textContent = S.stop + ' · 0.0 s'; $('recNote').textContent = S.recording; followStart();
   TK = setInterval(() => { $('recBtn').textContent = S.stop + ' · ' + ((Date.now() - T0) / 1000).toFixed(1) + ' s'; if (Date.now() - T0 > 45000 && mr.state === 'recording') mr.stop(); }, 200); }
  catch (e) { RBUSY = false; if (st) st.getTracks().forEach(t => t.stop()); err(S.micErr + e.message); } };
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
  try { const q = new URLSearchParams({words: LINE.text, job: 1}); if (REC && LINE.t0 != null) { q.set('ref', REC); q.set('t0', LINE.t0); q.set('t1', LINE.t1); } if (P && P.s.ln && P.s.ln[LINE.k]) q.set('nikud', P.s.ln[LINE.k]); if (P && P.id) q.set('pid', P.id); if (VC && VC.pairs && VC.pairs.length) q.set('vc', VC.pairs.join(','));
   const post = () => fetch(url('/check?' + q), {method: 'POST', body: TAKE.blob, headers: {'content-type': TAKE.blob.type || 'application/octet-stream'}});
   let r; try { r = await post(); } catch (e) { if (APIS.length <= 1) throw e; SRV = await pickApi(); r = await post(); }   // the chosen server went away: ask the others once
   let j = await r.json(); if (!r.ok || j.err) throw new Error(j.err || ('server said ' + r.status));
   if (j.job) j = await waitJob(j.job); RESULT = j; HIDDEN = new Set(); SHARED = false; $('share').hidden = true; $('shareP').textContent = S.shareQ; $('shareRow').hidden = false; $('askMsg').textContent = ''; render(j); saveHist(); if (typeof opts.onResult === 'function') { try { opts.onResult(j, {pid: P.id, line: LINE.k, rec: REC, strict: STRICT}); } catch (e) {} } }
  catch (e) { err(S.failed + e.message); }
  $('busy').hidden = true; $('check').disabled = false; };
 /* ----- the verdicts (the same rule as the Space's page) ----- */
 let CLEAN = false;
 function markOf(y, f) { const n = y && y.n || 0, sk = y && y.skel != null ? y.skel : null, ft = f && f.fit != null ? f.fit : null; if (!n || sk == null) return ''; const kp = y && y.kept != null ? y.kept : null, pw = y && y.pw != null ? y.pw : null, hs = y && y.hskel != null ? y.hskel : null;
  const sure = CLEAN && kp != null && kp >= .75 && hs != null && hs >= .6 && (pw == null || pw < .8);
  if (n >= 2) { if (sk < .2 && (ft == null || ft < .15)) { if (ft == null && CLEAN && !(kp != null && kp < .75)) return 'unsure'; if (!CLEAN && kp != null && kp >= .5) return 'unsure'; return 'off'; } if (CLEAN && pw != null && pw >= .95 && (ft == null || ft < .5)) return 'off'; if (sure) return 'ok'; if (sk < .4 || (ft != null && ft < .2) || (kp != null && kp < .5) || (pw != null && pw >= .8)) return 'unsure'; return 'ok'; } return sk < .2 && !sure ? 'unsure' : 'ok'; }
 /* whole-line evidence on a clean take (server: order.py); thresholds from exam_alouf.py — kept in step with index.html */
 const RULE = {drop: 10, margin: 4, swap: 8, rival: 0.3, altFit: 0.4, hear: 0.3, share: 0.35, half: 0.5, swap2: 12};
 function headMedian(TW) { let hs = TW.filter(t => (t.n || 0) >= 2 && t.hskel != null).map(t => t.hskel).sort((a, b) => a - b); if (!hs.length) return null; if (hs.length >= 3) hs = hs.slice(1); return hs[Math.floor((hs.length - 1) / 2)]; }
 function marksOf(TW, F, gap, rival) { const marks = TW.map((t, i) => markOf(t, F && F[i])); const why = TW.map(() => null); let lineWrong = false, cantHear = false;
  if (CLEAN) { const ds = TW.map(t => t.drop == null ? -1e9 : t.drop); const top = ds.indexOf(Math.max(...ds)); const second = Math.max(...ds.filter((d, i) => i !== top), -1e9);
   const dropped = top >= 0 && (TW[top].n || 0) >= 2 && ds[top] >= RULE.drop && ds[top] - second >= RULE.margin; const heard = dropped && (TW[top].skel || 0) >= .8 && (TW[top].kept || 0) >= .6;
   if (dropped && !heard) { marks[top] = 'off'; why[top] = 'dropped'; } else if (dropped && marks[top] === 'ok') marks[top] = 'unsure';
   const sw = TW.slice(0, -1).map(t => t.swap == null ? -1e9 : t.swap); if (sw.length) { const j = sw.indexOf(Math.max(...sw)), na = TW[j].n || 0, nb = TW[j + 1].n || 0; const pd = Math.max(ds[j], ds[j + 1]), same = pd >= RULE.drop && sw[j] < RULE.share * pd; if (sw[j] >= RULE.swap && Math.max(na, nb) >= 2 && Math.min(na, nb) >= 1 && !same) { marks[j] = 'off'; marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'; } }
  } else if (TW.length) {
   const m = headMedian(TW); const sw = TW.slice(0, -1).map(t => t.swap == null ? -1e9 : t.swap); if (m != null && m >= RULE.half && sw.length) { const j = sw.indexOf(Math.max(...sw)), na = TW[j].n || 0, nb = TW[j + 1].n || 0; const ds = TW.map(t => t.drop == null ? -1e9 : t.drop), pd = Math.max(ds[j], ds[j + 1]), same = pd >= RULE.drop && sw[j] < RULE.share * pd; if (sw[j] >= RULE.swap2 && Math.max(na, nb) >= 2 && Math.min(na, nb) >= 1 && !same) { marks[j] = 'off'; marks[j + 1] = 'off'; why[j] = why[j + 1] = 'swapped'; } }
  }
  const rg = rival && rival.gain != null ? rival.gain : null, rh = rival && rival.head != null ? rival.head : null;
  if (TW.length && gap != null && rg != null && rg >= RULE.rival && (gap - rg) <= RULE.altFit && (rh == null || rh >= RULE.hear)) { lineWrong = true; for (let i = 0; i < marks.length; i++) if (marks[i] === 'ok') marks[i] = 'unsure'; }
  if (TW.length && !CLEAN && !lineWrong) { const m = headMedian(TW); if (m != null && m < RULE.hear) { cantHear = true; for (let i = 0; i < marks.length; i++) if (marks[i] === 'off') marks[i] = 'unsure'; } }
  return {marks, why, lineWrong, cantHear}; }
 /* strict: on a clean take every 'not sure' word counts as not clearly right. Alouf exam (Rabbi Alouf against his own recording): wrong words
    caught 76% -> 89%, good words ✕ 0 -> 0.4%. That 0.4% is not general: on clean takes by other voices the committed exam rows give about 21%
    of good words ✕ (archive, 18 of 86) and 9.5% (Israeli readers), and on every archive take, clear or not, 32% (168/528) — hence strict only
    on clear takes; on an unclear take nothing changes and the page asks for a clearer take. Server: rule.strict_of */
 function strictOf(marks, why, clean, cantHear) { if (!clean || cantHear) return {marks, why, on: false}; return {marks: marks.map(m => m === 'unsure' ? 'off' : m), why: why.map((w, i) => marks[i] === 'unsure' && w == null ? 'unclear' : w), on: true}; }
 const VCLS = {throat: 'good', plain: 'bad', unsure: 'warn'};
 const thLead = t => !t || !t.v ? '–' : t.v === 'throat' ? S.thThroat : t.v === 'plain' ? (t.c === 'ע' ? S.thAlef : S.thPlain) : S.thUnsure;
 function render(j) { const W = j.words, TW = j.take.words, RW = j.ref ? j.ref.words : null, F = (j.fit && j.fit.length) ? j.fit : null;
  const HM = headMedian(TW); CLEAN = HM != null && HM >= .7;
  let {marks, why, lineWrong, cantHear} = marksOf(TW, F, j.take.gap, j.take.rival);
  const noSpeech = (j.take.phones || []).length < Math.max(3, 0.5 * (j.take.dur || 0)); if (noSpeech) { marks = marks.map(m => m ? 'unsure' : m); why = why.map(() => null); lineWrong = false; cantHear = false; }
  /* M0: the marks before strict — the notes, the throat colours and rows and the shva underline follow it, so a word strict newly
     flags keeps its evidence; the word's colour, label and the summary follow the strict marks */
  const M0 = marks.slice(); let SON = false; if (STRICT && !noSpeech) { const st = strictOf(marks, why, CLEAN, cantHear); marks = st.marks; why = st.why; SON = st.on; }
  const strictUnclear = STRICT && !CLEAN && !noSpeech && !cantHear && !lineWrong;
  if (!CLEAN) TW.forEach(t => (t.throat || []).forEach(th => { if (th.v === 'plain') { th.raw = 'plain'; th.v = 'unsure'; } })); const LABEL = {ok: S.labelOk, unsure: S.labelUnsure, off: S.labelOff, '': ''};
  const lab = i => why[i] === 'unclear' ? S.labelUnclear : LABEL[marks[i]];
  $('res').innerHTML = W.map((w, i) => { const t = TW[i]; let n = 0; const ths = (t.throat || []); const cls = () => { const th = ths[n++]; if (!th || !NOTES.l || M0[i] === 'off' || cantHear || noSpeech) return ''; if (th.v === 'plain') { const r = RW && RW[i] && (RW[i].throat || []).find(x => x.k === th.k); if (r && r.v === 'plain') return ''; } if (SON && th.v === 'unsure') return 'bad'; return VCLS[th.v] || ''; };
   return `<button class="dk-w ${marks[i]}" type="button" data-i="${i}" lang="he"><b>${hiW(w, cls, new Set(((NOTES.v && CLEAN && M0[i] !== 'off' && !cantHear && !noSpeech) ? ((j.shva && j.shva[i]) || []) : []).map(d => d.k)))}</b><small>${lab(i)}</small></button>`; }).join('');
  $('res').querySelectorAll('.dk-w').forEach(b => b.onclick = () => { const i = +b.dataset.i; $('res').querySelectorAll('.dk-w').forEach(x => x.classList.toggle('sel', x === b)); const r = RW && RW[i], f = F && F[i], t = TW[i];
   const mine = f && f.t0 != null ? [f.t0, f.t1] : t && t.t0 != null ? [t.t0, t.t1] : null;
   if (r && LINE.t0 != null) { playHim(LINE.t0 + r.t0 - .1, LINE.t0 + r.t1 + .1); const wait = (r.t1 - r.t0 + .4) * 1000; setTimeout(() => { if (mine) playYou(Math.max(0, mine[0] - .15), mine[1] + .15); }, wait + 150); }
   else if (mine) playYou(Math.max(0, mine[0] - .15), mine[1] + .15); });
  const VN = j.vowel_names || {}; const vname = k => esc((VN[k] || k).split(' ')[0]); const lines = [], allNotes = [];
  W.forEach((w, i) => { const t = TW[i]; const parts = []; if (cantHear || noSpeech) return;
   if (why[i] === 'swapped') { if (i + 1 < W.length && why[i + 1] === 'swapped' && TW[i].swap != null && TW[i].swap >= RULE.swap) parts.push(fmt(S.swapped, {a: he(w), b: he(W[i + 1])})); }
   else if (why[i] === 'unclear') parts.push(S.wUnclear); else if (marks[i] === 'off') parts.push(S.wOff); else if (marks[i] === 'unsure') parts.push(S.wUnsure);
   if (marks[i] && marks[i] !== 'ok' && t.miss && t.miss.length && t.miss.length < (t.n || 9)) parts.push(he(t.miss.join(' ')) + S.notHeard);
   if (NOTES.l && M0[i] !== 'off') (t.throat || []).forEach(th => { if (th.v !== 'plain') return; const r = RW && RW[i] && (RW[i].throat || []).find(x => x.k === th.k); if (r && r.v === 'plain') return; parts.push((th.c === 'ע' ? S.ayinAlef : S.hetPlain) + practice(th.c)); });
   if (NOTES.l && SON && M0[i] !== 'off') (t.throat || []).forEach(th => { if (th.v === 'unsure') parts.push((th.c === 'ע' ? S.ayinUnclear : S.hetUnclear) + practice(th.c)); });
   if (NOTES.l) (t.notes || []).forEach(nn => { if (nn.say === 'sav') parts.push(S.tavSamekh + practice('ת')); });
   const vOK = NOTES.v && CLEAN && M0[i] !== 'off'; const vd = vOK ? ((j.vowels && j.vowels[i]) || []) : [], vn = vOK ? ((j.vowels_nikud && j.vowels_nikud[i]) || []) : [];
   vd.forEach(d => parts.push(fmt(S.vowHaz, {you: vname(d.you), ref: vname(d.ref)}))); vn.forEach(d => { if (!vd.some(x => x.k === d.k)) parts.push(fmt(S.vowNik, {you: vname(d.you), ref: vname(d.ref)})); });
   const sv = vOK ? ((j.shva && j.shva[i]) || []) : []; sv.forEach(d => { const SW = S.shvaWhy || {}, why = SW[d.rule] || SW.hazzan; parts.push(fmt(d.want === 'vowel' ? S.shvaNa : S.shvaNah, {c: he(d.c)}) + (why ? ' — ' + esc(why) : '')); });   /* v4.9 servers */
   if (!parts.length) return; const txt = (() => { const d = document.createElement('div'); d.innerHTML = parts.join('; '); return d.textContent; })(), key = i + '|' + txt;
   allNotes.push({i, w, text: txt}); if (HIDDEN.has(key)) return;
   lines.push(`<li data-key="${esc(key)}">${he(w)}: ${parts.join('; ')}.<button class="dk-x" type="button" title="${esc(S.dismiss)}" aria-label="${esc(S.dismiss)}">×</button></li>`); });
  const offW = W.filter((w, i) => marks[i] === 'off'), unsW = W.filter((w, i) => marks[i] === 'unsure'), say = $('say');
  if (noSpeech) { say.className = 'dk-say warn'; say.textContent = S.noSpeech; }
  else if (lineWrong) { say.className = 'dk-say bad'; say.textContent = S.wrongLine; }
  else if (cantHear) { say.className = 'dk-say warn'; say.textContent = S.cantHear; }
  else if (strictUnclear) { say.className = 'dk-say warn'; say.textContent = S.strictUnclear; }
  else if (!F && j.ref_err && !/Tehillim/.test(j.ref_err)) { say.className = 'dk-say warn'; say.textContent = S.noRef; }
  else if (!lines.length) { say.className = 'dk-say ok'; say.textContent = F ? S.allOkRef : S.allOk; }
  else if (offW.length) { say.className = 'dk-say bad'; say.innerHTML = fmt(SON ? S.someOffStrict : S.someOff, {n: W.length - offW.length, N: W.length, off: offW.map(he).join(', ')}) + (unsW.length ? fmt(S.notSure, {uns: unsW.map(he).join(', ')}) : '') + '.'; }
  else if (unsW.length) { say.className = 'dk-say warn'; say.innerHTML = fmt(S.unsureOnly, {uns: unsW.map(he).join(', ')}); }
  else { say.className = 'dk-say warn'; say.textContent = S.few; }
  $('notes').innerHTML = lines.join('');
  $('notes').querySelectorAll('.dk-x').forEach(b => b.onclick = () => { const li = b.closest('li'); HIDDEN.add(li.dataset.key); li.remove(); if (!SHARED && TAKE && keeps()) $('share').hidden = false; });
  $('askBtn').hidden = !keeps() || !$('askForm').hidden;
  LAST = {ok: marks.filter(m => m === 'ok').length, n: W.length, marks: marks.slice(), notes: allNotes};
  $('bothLine').hidden = !(REC && LINE && LINE.t0 != null && TAKE_URL); showHist();
  const rows = []; TW.forEach((t, i) => { if (M0[i] === 'off' || cantHear || noSpeech) return; (t.throat || []).forEach(th => { const r = RW && RW[i] && (RW[i].throat || []).find(x => x.k === th.k); rows.push({w: W[i], c: th.c, you: th, him: r}); }); });
  if (rows.length && NOTES.l) { $('th').innerHTML = rows.map(x => `<div class="dk-tr"><div><span class="dk-lt">${esc(x.c)}</span><span>${he(x.w)}</span></div><div><span class="dk-k">${esc(S.you)}</span><span class="${SON && x.you.v === 'unsure' ? 'bad' : VCLS[x.you.v] || ''}">${esc(SON && x.you.v === 'unsure' ? S.thUnclear : thLead(x.you))}</span></div><div><span class="dk-k">${esc(S.hazzan)}</span><span>${esc(thLead(x.him))}</span></div></div>`).join(''); $('thP').hidden = false; } else $('thP').hidden = true;
  fold('s3'); $('s4').hidden = false; $('s4').querySelector('.dk-body').hidden = false; scrollTo('s4'); }
 const sb = $('strict'); sb.checked = STRICT; sb.onchange = () => { STRICT = sb.checked; try { localStorage.setItem('dk.strict', STRICT ? '1' : '0'); } catch (e) {} if (RESULT) render(RESULT); };
 $('againLine').onclick = () => { resetTake(); openStep('s3'); scrollTo('s3'); };
 /* ----- v5: live follow-along (Tarteel): while recording, the words light up as they are sung — only on a fast server
    (the Mac's GPU: SRV.device mps/cuda), or when the page asks for it (follow: true); never on a slow one ----- */
 let FTK = null, FBUSY = false;
 const followOn = () => opts.follow === true || opts.follow === '1' || (opts.follow !== false && opts.follow !== '0' && SRV && SRV.follow && /mps|cuda/.test(String(SRV.device || '')));
 function followShow(done) { if (!LINE) return; $('lineWords').innerHTML = heWords(LINE.text).map((w, i) => `<span class="dk-fw${i < done ? ' on' : ''}">${hiTh(w)}</span>`).join(' '); }
 /* each call re-sends the whole take so far, so the wait grows with it: 1.5 s, then a quarter of the take's length (a 40 s take: ~12 calls, not 26) */
 function followStart() { if (!followOn() || !LINE) return; followShow(0);
  const tick = () => { FTK = setTimeout(() => { if (!MR || MR.state !== 'recording') return; tick(); if (FBUSY || !CH.length) return; FBUSY = true;
   fetch(url('/follow?' + new URLSearchParams({words: LINE.text})), {method: 'POST', body: new Blob(CH, {type: MR.mimeType || 'audio/mp4'})})
    .then(r => r.ok ? r.json() : null).then(j => { if (j && j.n && MR && MR.state === 'recording') followShow(j.done); }).catch(() => {}).finally(() => { FBUSY = false; }); }, Math.max(1500, .25 * (Date.now() - T0))); }; tick(); }
 function followStop() { clearTimeout(FTK); FTK = null; if (LINE) $('lineWords').innerHTML = hiTh(LINE.text); }
 /* ----- v5: what to check ----- */
 $('nLet').checked = NOTES.l; $('nVow').checked = NOTES.v;
 const saveNotes = () => ls('dk.notes', (NOTES.l ? 'l' : '') + (NOTES.v ? 'v' : '') || '-');
 $('nLet').onchange = () => { NOTES.l = $('nLet').checked; saveNotes(); if (RESULT) render(RESULT); };
 $('nVow').onchange = () => { NOTES.v = $('nVow').checked; saveNotes(); if (RESULT) render(RESULT); };
 /* ----- v5: the hazzan, then you (Fahm's side by side) ----- */
 $('bothLine').onclick = () => { if (!LINE || LINE.t0 == null) return; playHim(LINE.t0, LINE.t1); setTimeout(() => playYou(0, null), (LINE.t1 - LINE.t0 + .5) * 1000); };
 /* ----- v5: your tries on this line (kept in this browser) ----- */
 const histKey = () => P && LINE ? 'dk.hist.' + P.id + '.' + LINE.k : null;
 function saveHist() { const k = histKey(); if (!k || !LAST.n) return; let H = []; try { H = JSON.parse(ls(k) || '[]'); } catch (e) {} H.push({t: Date.now(), ok: LAST.ok, n: LAST.n}); ls(k, JSON.stringify(H.slice(-20))); showHist(); }
 function showHist() { const k = histKey(); let H = []; try { H = JSON.parse(ls(k) || '[]'); } catch (e) {} $('hist').textContent = H.length > 1 ? S.histL + H.slice(-5).map(h => h.ok + '/' + h.n).join(' · ') + (H[H.length - 1].ok === H[H.length - 1].n ? ' ✓' : '') : ''; }
 /* ----- v5: hide a wrong note, and with a yes send the take (Tarteel) ----- */
 const metaOf = extra => ({pid: P && P.id, line: LINE && LINE.k, words: LINE && LINE.text, nikud: P && P.s.ln && LINE ? P.s.ln[LINE.k] : null, ref: REC, t0: LINE && LINE.t0, t1: LINE && LINE.t1,
  marks: LAST.marks, notes: LAST.notes.map(x => x.w + ': ' + x.text).slice(0, 30), strict: STRICT, voice_card: VC && VC.pairs, server: RESULT && RESULT.server, device: String(navigator.userAgent || '').slice(0, 120), ...extra});
 /* the send-it prompt and "Ask a hazzan": a server before v5 has no /review or /feedback, and one whose own disk is temporary (the Space)
    loses them at its next restart — a GitHub mirror only pushes, so 'durable' is not enough: the takes must be 'persistent' */
 const keeps = () => !!(SRV && SRV.reviews && SRV.storage && SRV.storage.takes === 'persistent');
 /* a 5.2+ server reads the meta (contact, question) from a header, so its access log never records it; older ones only from the query */
 const postMeta = (path, meta) => { const m = encodeURIComponent(JSON.stringify(meta)), hd = !!(SRV && +SRV.version >= 5.2);
  return fetch(url(path + (hd ? '' : '?meta=' + m)), {method: 'POST', body: TAKE.blob, headers: Object.assign({'content-type': TAKE.blob.type || 'application/octet-stream'}, hd ? {'x-dk-meta': m} : {})}); };
 $('shareNo').onclick = () => { SHARED = true; $('share').hidden = true; };
 $('shareYes').onclick = async () => { if (!TAKE) return; $('shareYes').disabled = true;
  try { const dis = LAST.notes.filter(x => HIDDEN.has(x.i + '|' + x.text)).map(x => ({i: x.i, word: x.w, text: x.text})); const r = await postMeta('/feedback', metaOf({dismissed: dis})); const jj = await r.json(); if (!r.ok || jj.err) throw new Error(jj.err || r.status);
   SHARED = true; $('shareP').textContent = S.shareDone; $('shareRow').hidden = true; }
  catch (e) { $('shareP').textContent = S.shareFail + e.message; }
  $('shareYes').disabled = false; };
 /* ----- v5: ask a hazzan (Qara'a): the take and a question, answered on the server's /hazzan page ----- */
 const qsLoad = () => { try { return JSON.parse(ls('dk.reviews') || '[]'); } catch (e) { return []; } };
 $('askBtn').onclick = () => { $('askForm').hidden = false; $('askBtn').hidden = true; $('askMsg').textContent = ''; $('askNote').focus(); };
 $('askCancel').onclick = () => { $('askForm').hidden = true; $('askBtn').hidden = false; };
 $('askSend').onclick = async () => { if (!TAKE || !LINE || !RESULT) return; $('askSend').disabled = true;
  try { const r = await postMeta('/review', metaOf({note: $('askNote').value.slice(0, 1000), contact: $('askContact').value.slice(0, 200), say: $('say').textContent})); const jj = await r.json(); if (!r.ok || jj.err) throw new Error(jj.err || r.status);
   const Q = qsLoad(); Q.unshift({id: jj.id, token: jj.token, api: API, words: LINE.text, t: Date.now()}); ls('dk.reviews', JSON.stringify(Q.slice(0, 20)));
   $('askMsg').textContent = S.askSent; $('askForm').hidden = true; $('askBtn').hidden = false; $('askNote').value = ''; refreshQs(); }
  catch (e) { $('askMsg').textContent = S.askFail + e.message; }
  $('askSend').disabled = false; };
 async function refreshQs() { const Q = qsLoad(); if (!Q.length) { $('qs').hidden = true; return; }
  const got = await Promise.all(Q.map(async q => { try { const r = await fetch(q.api + '/review/' + q.id + '?t=' + encodeURIComponent(q.token), {cache: 'no-store'}); if (r.status === 404) return {q, gone: true}; return {q, j: await r.json()}; } catch (e) { return {q}; } }));
  const ans = got.filter(g => g.j && g.j.state === 'answered').length;
  $('qs').innerHTML = `<h4>${esc(S.askMine)}${ans ? ` · <span class="dk-new">${ans} ${esc(S.askAnswered)}</span>` : ''}</h4>` + got.map(g => `<div class="dk-q"><div>${he(g.q.words)}</div>`
   + (g.gone ? `<small>${esc(S.askGone)}</small>` : g.j && g.j.state === 'answered' ? `<p class="dk-ans">${esc(g.j.reply.text)}</p><small>${esc(g.j.reply.by || '')}</small>` : `<small>${esc(S.askWaiting)}</small>`)
   + ` <a class="dk-prac" href="${esc(g.q.api + '/review/' + g.q.id + '/audio?t=' + encodeURIComponent(g.q.token))}" target="_blank" rel="noopener">${esc(S.askPlay)}</a></div>`).join('');
  $('qs').hidden = false; }
 refreshQs();
 /* ----- v5: the voice card ----- */
 function vcShow() { $('vcState').innerHTML = VC ? ' · ' + esc(S.vcOn) + ` <button class="dk-link" type="button" data-r="vcForget">${esc(S.vcForget)}</button>` : '';
  const f = $('vcForget'); if (f) f.onclick = () => { VC = null; ls('dk.vc', null); vcShow(); }; }
 vcShow(); let VCT = null, VMR = null, VT0 = 0, VTK = null, VBUSY = false;   // VBUSY: as RBUSY, for the voice card's recorder
 $('vcOpen').onclick = async () => { await loadLyrics(); const t = LY && LY.s && LY.s.t23; if (!t || !t.ln || t.ln.length < 2) { err(S.vcNoText); return; }
  VCT = {words: t.l[0] + ' ' + t.l[1], nikud: t.ln[0] + ' ' + t.ln[1]}; $('vcText').innerHTML = esc(t.ln[0]) + '<br>' + esc(t.ln[1]); $('vcSay').textContent = ''; $('vcSay').className = 'dk-say'; $('vc').hidden = false; scrollTo('vc'); };
 $('vcClose').onclick = () => { $('vc').hidden = true; };
 $('vcRec').onclick = async () => { if (VMR && VMR.state === 'recording') { VMR.stop(); return; } if (VBUSY) return; VBUSY = true; let st = null;
  try { st = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
   const mt = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', ''].find(x => !x || MediaRecorder.isTypeSupported(x)), ch = []; const mr = new MediaRecorder(st, mt ? {mimeType: mt} : undefined); VMR = mr; mr.ondataavailable = e => { if (e.data.size) ch.push(e.data); };
   mr.onstop = () => { VBUSY = false; st.getTracks().forEach(x => x.stop()); clearInterval(VTK); $('vcRec').textContent = S.record; vcCheck(new Blob(ch, {type: mr.mimeType || 'audio/mp4'})); };
   mr.start(250); VT0 = Date.now(); $('vcSay').textContent = ''; $('vcRec').textContent = S.stop + ' · 0.0 s';
   VTK = setInterval(() => { $('vcRec').textContent = S.stop + ' · ' + ((Date.now() - VT0) / 1000).toFixed(1) + ' s'; if (Date.now() - VT0 > 40000 && mr.state === 'recording') mr.stop(); }, 200); }
  catch (e) { VBUSY = false; if (st) st.getTracks().forEach(x => x.stop()); err(S.micErr + e.message); } };
 async function vcCheck(blob) { if (!VCT) return; const b = $('vcBusy'); b.hidden = false; b.innerHTML = '<span class="dk-spin"></span><span>' + esc(S.vcBusy) + '…</span>'; $('vcRec').disabled = true;
  try { const r = await fetch(url('/check?' + new URLSearchParams({words: VCT.words, nikud: VCT.nikud, job: 1})), {method: 'POST', body: blob, headers: {'content-type': blob.type || 'application/octet-stream'}});
   let j = await r.json(); if (!r.ok || j.err) throw new Error(j.err || r.status);
   for (let i = 0; j.job && i < 300; i++) { await new Promise(z => setTimeout(z, 1500)); const st = await (await fetch(url('/job/' + j.job), {cache: 'no-store'})).json(); if (st.state === 'done') j = st.result; else if (st.state === 'error' || st.state === 'gone') throw new Error(st.err || 'error'); }
   const hm = headMedian(j.take.words); const say = $('vcSay');
   if (hm == null || hm < .7) { say.className = 'dk-say warn'; say.textContent = S.vcUnclear; }
   else { const ok = new Set(['U>O', 'O>U', 'E>I', 'I>E']), pairs = new Set(); Object.values(j.vowels_nikud || {}).forEach(ds => ds.forEach(d => { const p = d.ref + '>' + d.you; if (ok.has(p)) pairs.add(p); }));
    VC = {pairs: [...pairs], head: Math.round(hm * 100) / 100, t: Date.now()}; ls('dk.vc', JSON.stringify(VC)); vcShow();
    say.className = 'dk-say ok'; say.textContent = VC.pairs.length ? fmt(S.vcDone, {pairs: VC.pairs.map(p => (S.vcPair || {})[p] || p).join(', ')}) : S.vcNothing; } }
  catch (e) { $('vcSay').className = 'dk-say bad'; $('vcSay').textContent = S.failed + e.message; }
  b.hidden = true; $('vcRec').disabled = false; }
 $('otherLine').onclick = () => { openStep('s2'); scrollTo('s2'); };
 health();
 return {open: id => { LY ? openP(id) : null; }, get result() { return RESULT; }};
}
window.Dikduk = Object.assign(window.Dikduk || {}, {mount, strings: (window.Dikduk && window.Dikduk.strings) || {}, version: '5.2'});
function auto() { document.querySelectorAll('[data-dikduk]').forEach(el => { if (el.dataset.dkMounted) return; el.dataset.dkMounted = '1'; mount(el, {api: el.dataset.api, pz: el.dataset.pz, th: el.dataset.th, line: el.dataset.line, rec: el.dataset.rec, archive: el.dataset.archive, strict: el.dataset.strict, letters: el.dataset.letters, follow: el.dataset.follow, notes: el.dataset.notes}); }); }   // data-api may hold several servers, space-separated
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto); else auto();
})();
