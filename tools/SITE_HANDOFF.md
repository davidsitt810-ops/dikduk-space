# Dikduk checker → thepizmonim.com — handoff to the site chat

From the dikduk chat, Oct 22, 2026. David asked for the checker to ship on the site. The checker is a separate
server; the site only links to it. **The dikduk chat never touches the site or its deploy chain — everything below is
for the site chat to do in its own way.**

## What it is

A page where a person picks a pizmon line (or a Tehillim pasuk), hears the hazzan, records themselves singing or
reading it, and gets, word by word: did each word come through, did each ע and ח come from the throat, and (as a
hint) whether the vowels matched the hazzan / the nikud. Phone-first, iPhone Safari tested. Nothing is stored
when someone uses it.

It runs on a Hugging Face Space David owns (`davidsitt/pizmonim-dikduk`, PRO account, CPU). The site needs no
server work and no keys.

## Addresses

| | |
|---|---|
| Public page (use this one) | `https://davidsitt-pizmonim-dikduk.hf.space/try` |
| Open on a pizmon | `…/try?pz=200` |
| Open on a pizmon **and a line** | `…/try?pz=200&line=3` (1-based line of the site's lyrics for that pizmon) |
| Open on a Tehillim pasuk | `…/try?th=23&line=1` |
| Pick which hazzan recording to compare with | `…&rec=200%20Dodi.mp3` (an archive file name; default = the site's main recording `b`) |
| Health (JSON) | `https://davidsitt-pizmonim-dikduk.hf.space/health` |

Pizmon ids and line numbers are the site's own: the checker reads the site's `lyrics.json` (`s[id].l` lines, `t`
sync events, `b` best recording) from the `holiday` preview URL, so what the site calls line 3 is line 3 here.

## Two ways to put it on the site — David wants the second

**A. A link** (five minutes): a button "Check my singing (beta)" on each pizmon page opening `…/try?pz=<id>`
(or `…/try?pz=<id>&line=<k>`) in a new tab. The visitor sees the checker's own page on the Space.

**B. Part of the site itself** (what David asked for): the checker rendered inside a page of thepizmonim.com —
e.g. `thepizmonim.com/dikduk`, or a panel on each pizmon page — in the site's own fonts and colours. One script and
one `<div>`; the script draws the whole guided flow (what to sing → pick a line → record → how it went) and talks
to the brain on the Space over the network (CORS is open). Nothing of Hugging Face is visible to the visitor.

```html
<div id="dikduk" data-dikduk data-api="https://davidsitt-pizmonim-dikduk.hf.space" data-pz="200" data-line="3"></div>
<script src="/dikduk/embed.js"></script>
```

- Get `embed.js` from `https://davidsitt-pizmonim-dikduk.hf.space/embed.js` (34 KB, no dependencies) and copy it
  into the site's own files — do not load it live from the Space (when the Space sleeps the script would wait
  with it). The source of truth is `static/embed.js` in github.com/davidsitt810-ops/dikduk-space; the dikduk
  chat says when a new version is worth copying over.
- `data-pz` / `data-th` + `data-line` open it on a text and a line (omit them for the full chooser);
  `data-rec="200 Dodi.mp3"` picks the hazzan recording. Or mount from code:
  `Dikduk.mount(el, {api, pz, line, rec, lyrics, onResult})` — pass the site's already-loaded `lyrics` object to
  save a fetch; `onResult(result, {pid, line, rec})` fires after each check if the site wants to do anything with it.
- Styling: everything lives under `.dk`; set CSS variables on the container — `--dk-bg --dk-panel --dk-line
  --dk-fg --dk-mute --dk-accent --dk-good --dk-warn --dk-bad --dk-ink --dk-he --dk-ui`. The site's fonts are
  inherited unless `--dk-he` (Hebrew) / `--dk-ui` are set. Every piece of text is in `Dikduk.strings` (override
  before mounting) — a Hebrew UI is a strings file away.
- It uses no browser storage and never touches `PZ_JT9` / `PZB9_SRC`. The microphone works because the page is on
  the site's own HTTPS origin (no iframe, no `allow` attribute). Tested on a demo page with a different theme and
  fonts: `site_demo.html` in the dikduk chat (screenshot attached to the handoff message).
- Label it **beta**. Suggested line above it: *"Sing a line into your phone; it tells you which words came through
  and whether each ע and ח came from the throat. New — tell us when it's wrong."*

If you'd rather write the page yourselves, the API is five calls (appendix). The script is the reference
implementation of exactly that, and the word-verdict rule (`markOf`) is in it.

## Things to know before it faces people

- **Beta accuracy** (v4.6, Oct 24; measured on hazzanim and on Israelis reading, not yet on students). Clean
  a-cappella reading (Rabbi Alouf's Tehillim, 150 pesukim, 4,140 right words): no right word marked "not heard"; a
  skipped word caught 97–98%, swapped words 96–99%, a replaced word 70–77%, the wrong pasuk 149 of 149 ("This does
  not sound like this line") and never a right one. Voices the ears never heard (Israelis reading, no hazzan): a
  right word red about 1% (mostly words the transcript writes in digits or Latin letters), "not sure" a fifth, no
  right sentence called the wrong line, the wrong sentence called 3 times in 4. Another hazzan singing a pizmon
  with instruments against the site's reference (the archive's second recordings): a right word red 2% — words the
  singer does not sing as written — and "not sure" about half. ע said like alef caught ~2/3 (a third "not sure"); ח
  better; vowel notes only on a clean take, and a hint only. It says "not sure" rather than accuse. Two more
  headlines it can give: "I did not hear any singing" (silence, noise) and "I could not make out the words of this
  line" (far from the phone, music, or the wrong text) — both flag nothing.
- **Speed**: 15–30 s per check. One check at a time on the small machine: two people at once, the second waits.
  If use grows, David upgrades the Space's hardware in one click (CPU upgrade ≈ $0.03/h; a GPU answers in 2 s).
- **Sleep**: after 48 idle hours the server sleeps; the first visitor waits about a minute (the page says
  "Waking the server…"). Normal.
- **Nothing to configure on the site**: the page updates itself (served from GitHub); server updates mean a
  15-minute reboot David does, during which the page shows "Server not reachable".
- **Do not** proxy or copy the page into the site; link to it. Its API (`POST /check`, `GET /lyrics`, `GET /ref`,
  CORS open) exists for a deeper integration later — a site-native page calling the checker — once it has proven
  itself. Ask the dikduk chat for the API note when that day comes.
- The checker keeps its own browser storage keys (`dk.*`); it never touches `PZ_JT9` or `PZB9_SRC`.

## Also in this handoff: Rabbi Alouf's Tehillim

`tehillim-alouf-site-package.zip` (in David's `Downloads/dikduk-v4/`): 144 perakim of Rabbi Alouf's reading with
pasuk and word timings, `lyrics_tehillim.json` in the site's lyrics shape (all 150 perakim with words and nikud; 6
have text only), `tehillim_songs.json` records for the index (section Tehillim), the renamed mp3s already on
David's Mac (`~/Downloads/Tehilim/tehillim/`, 203 MB), and a README with the merge steps. The checker already
serves 8 of those perakim with audio and all 150 as text; when the site hosts the audio, the checker can point at
the site's copy instead (one setting), so there is one source of truth.

## Who to ask

Anything about the checker's behaviour, numbers, or API: the dikduk chat (David's). Anything about where the
button goes and how it looks: yours.

## Appendix — the brain's API (for a site-written page; `embed.js` is the reference)

Base: `https://davidsitt-pizmonim-dikduk.hf.space`. All JSON, CORS `*`. No keys.

- `GET /health` → `{ok, version, ears:{letter_head, vowel_head, tehillim_audio, tehillim_perakim:[…]}, …}`.
  The first call after a sleep takes up to a minute; show "waking the server…".
- `GET /lyrics` → the site's `lyrics.json` plus Tehillim entries `t1…t150` in the same shape (`l` lines, `ln` pointed
  lines, `t` sync events per recording, `b` main recording). The site already has its own copy for pizmonim; line
  times come from the sync events exactly as the sing-along does (deciseconds,lineIndex; the next event's time
  ends the line).
- `GET /ref?f=<recording file>&words=<line>&t0=&t1=` → analyses and caches the hazzan's line. Fire it when the
  visitor picks a line (while they record) so the check only has to listen to them.
- `POST /check?words=<line>&job=1[&ref=<f>&t0=&t1=][&nikud=<pointed line>]`, body = the audio blob as recorded
  (`audio/mp4` from iPhone Safari, webm from Chrome; any ffmpeg format), ≤ 40 s → `202 {job}`.
  Then `GET /job/<job>` every 1.5 s → `{state: queued|running|done|error, stage, queued, result}`.
- `result`: `{words:[…], take:{words:[{w, n, skel, hskel, kept, pw, miss:[letters not heard], throat:[{c, k, v:
  throat|plain|unsure}], vow:[…], t0, t1, phones}]}, ref?:{words:[{t0, t1, throat…}]}, fit?:[{fit, t0, t1}],
  vowels?:{i:[{k, you, ref}]}, vowels_nikud?:{…}, vowel_names:{…}}`. Word verdict (`markOf` in `embed.js`): with
  ≥2 consonants, "not heard" when `skel<.2` and `fit<.15` (or, on a clean take, `pw≥.95`); "not sure" when
  `skel<.4` or `fit<.2` or `kept<.5` or `pw≥.8`; else fine. One-consonant words are never flagged.
- **Two servers, the Mac mini first (v4.7)**: David's M4 Mac mini can run the same server at home behind a Cloudflare
  Tunnel (`mac/README_MAC.md` in the repo; hostname to be confirmed, planned `https://dikduk.thepizmonim.com`). The
  embed takes several servers and uses whichever answers `/health` first, re-asking the others if a check cannot
  reach the chosen one: `data-api="https://dikduk.thepizmonim.com https://davidsitt-pizmonim-dikduk.hf.space"`
  (or `api: [..]` in `mount`). Load the script from a CDN that is up even when a server is not:
  `<script src="https://cdn.jsdelivr.net/gh/davidsitt810-ops/dikduk-space@main/static/embed.js"></script>`
  (jsDelivr caches the branch for up to 12 h; `https://purge.jsdelivr.net/gh/davidsitt810-ops/dikduk-space@main/static/embed.js` refreshes). Until the Mac is up, the single Space URL works as before.
- **Letter checker** (v4.7): `GET /letters` is a ready page (one letter at a time: hear Rabbi Alouf, say it, ✓/✕/not
  sure); for a site-written version, `GET /letters.json` lists the letters, their variants and his example words
  (audio at `GET /letters/audio/<name>.mp3`, ~5 KB each), and `POST /letter?c=<letter>[&want=b|v|k|kh|p|f|sh|s]
  [&strict=1]` with a 2–3 s take as the body → `{v: right|wrong|unsure|no_speech, say, more, heard:[IPA], alouf,
  why, peak, ar_peak, win, dur, ms}`. The server judges only the take's opening sound. Measured numbers are in the
  README (v4.7) — roughly: Rabbi Alouf's own letters called right 80–98% and wrong 0–5%, Israeli-style ע ח ק caught
  74–89%.
- Hazzan audio: archive recordings play straight from `https://www.pizmonim.org/MP3/<file>` (seek to `t0`, stop at
  `t1`); Tehillim from `GET /tehillim/audio/tehillim-023.mp3` (144 perakim since Oct 23; when the site hosts the package's
  mp3s, the checker can be pointed at the site's copy).
