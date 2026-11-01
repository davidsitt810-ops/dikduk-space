---
title: Pizmonim dikduk fit-score
emoji: 🎤
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Pizmonim dikduk fit-score server

Answers one question about a recording of a pizmon line: **how well does the audio fit the sounds the hazzan
makes, word by word, and were the throat letters said from the throat?** Three ears, all deterministic (the same
bytes always give the same numbers): a phone recognizer (wav2vec2-xlsr-53-espeak-cv-ft) for the words, an
Arabic-letter recognizer (wav2vec2-large-xlsr-53-arabic) that writes ع / ح when it hears the throat, and a small
Hebrew-letter head (`letter_head.pt`) trained on the archive's own hazzanim, on the Arabic model's hidden features,
so ע/א and ח/כ are sounds it learned from them. Classifiers on the same features (`throat_models*.json`) add a
vote; "from the throat" needs two votes and none against. The hazzan's own archive recording is the yardstick,
not a dictionary.

v4 adds Rabbi Alouf's Tehillim (144 perakim, 5 hours, every pasuk aligned to its pointed text): the letter head
and the classifiers retrained with him, a vowel head (`full_head.pt`: letters + the five vowel classes A E I O U
from the nikud) that compares the student's vowels with the hazzan's or with the nikud, and the perakim themselves
in `/lyrics` (ids `t1`…`t150`), with their audio when the mp3s are in `static/tehillim/`.

v4.1 retrains the letter head on every synced archive recording (3,510 lines, 700 more recordings) plus Egyptian
Arabic read speech (FLEURS, CC BY 4.0: ع/ح from many throats, mapped onto Hebrew letters), adds a letters-heard
signal with per-letter "not heard" feedback, and a combined word score the page trusts on clean takes.

v4.2 runs on the Space davidsitt/pizmonim-dikduk: the Dockerfile pulls the code, the heads and `static/` from the
GitHub repo `davidsitt810-ops/dikduk-space` while building (push there, then rebuild the Space); a check is queued
(`/check?…&job=1`, polled at `/job/<id>`) so the proxy's request limit cannot cut a long first check; the page asks
for the hazzan's line as soon as a line is picked; torch uses the container's real CPU quota.

v4.3 adds whole-line evidence from the letter head (`order.py`): how much the audio prefers the line without each
word (a skipped word), with two neighbours the other way round (a swap), and what the written line costs against the
free path (another text). Measured on 70 of Rabbi Alouf's held-out pesukim, each intact and tampered four ways: a
skipped word caught 97%, swapped words 92% (was 45%), a replaced word 79%, a wrong line 100% at line level, and 0
false alarms on 1,850 right words. The ח vote uses the v2 classifier (all 79 of his ח from the throat; Israeli ח
said like כ: 92% plain, 0% throat); a plain ע/ח is a fault only where the hazzan says it from the throat; /record
is the recording booth and /embed.js the drop-in for a site page.

v4.4 (the Shabbat round, Oct 23–24) measures the pizmonim case too — the archive's own second recordings, another
hazzan with instruments, checked against the site's reference (`tools/exam_archive.py`, 87 right takes, 98 wrong
lines) — and fixes what it showed: a right word went red on 8.6% of those takes, because the per-word rule on a
poorly heard take trusted the phone recognizer twice (`skel`, `fit`) and never asked the letter head. Now (1) on a
take the heads hear poorly, red needs the head to agree (under half the letters heard); (2) the pw-red does not fire
when the hazzan's own sounds for the word were found (fit ≥ .5); (3) CLEAN leaves the lowest word out of the median
(one wrong word must not make a good recording look poor: swaps caught 92 → 99%, skipped 97 → 99% on Rabbi Alouf);
(4) the line gap speaks on every take, clean or not (0 false "wrong line" on 157 right takes); (5) a take whose head
median is under .3 is "I could not make out the words": nothing red, the doubtful words "not sure". Also: silence or noise says "I did not hear any
singing" (it used to be "not this line" with every word red); a skipped word is no longer called "swapped" with its
neighbour (the swap must gain ≥ 0.35 of the drop); the swap evidence works on half-heard takes too (head median
.5–.7, bar 12 nats). An independent review added: the skip-vs-swap guard uses the pair's own drop, the scoreboard scores by
position (repeated words), an empty fit is no hazzan, and CLEAN takes the true (lower-middle) median. Right words
red on the archive: 8.6% → 0.9% (4 of 456, words the singers do not sing as written), archive swaps caught 40 → 65%;
Rabbi Alouf: still 0 of 1,850 (and 0 of 2,290 on a fresh validation batch), skipped 97%, swapped 96%. The three copies of the rule (server, page, embed) are checked
word for word on every exam row by `tools/t_parity.py`. All 144 perakim of Rabbi Alouf's Tehillim are in
`static/tehillim/` (102 MB at 16 kHz / 48 kbps).

v4.5 (Oct 24) rebuilds the wrong-line verdict on the text's own lines (`order.rival_evidence`, `/check?pid=…`): another
line of the same perek or pizmon must beat the written one by 0.3 nats a frame and fit the audio itself. The free-path
gap, measured on 80 Israelis reading other sentences — voices the head reads poorly — called 33 of 80 right sentences
"not this line"; the rival test calls 0 of 80, and still 70/70 of Rabbi Alouf's wrong pesukim. A "plain" ע/ח and the
vowel notes are shown on clean takes only.

v4.6 (Oct 24, before dawn) ships the letter head retrained on other voices (`letter_head.pt`, head v7): 1,500 clips
of Israelis reading (FLEURS he_il train, ע written as א and ח as כ, as they say them) and 410 Egyptian Arabic clips
(ع ح from the throat) added to Rabbi Alouf and the archive. On Israelis reading: clean takes 2 → 15 of 80, "not sure"
32 → 21% of right words, swapped words caught 37 → 75%, the wrong sentence called 23 → 60 of 78; Rabbi Alouf
unchanged (0 false alarms of 2,290, skipped 98%, swapped 99%, wrong pasuk 79/79, ע 90% from the throat); the
pizmonim archive 0.9 → 2.0% right words red (words the singers do not sing as written). The wrong-line verdict also
asks that the other line be heard itself (its head median ≥ .3). `tools/exam_israeli_words.py` is the other-voices
exam; `tools/extract_il_train.py` and `train_head2.py … HEAD_IL=1 HEAD_EG=1` reproduce the head.

v4.7 (Oct 24, night) adds the **letter checker**: `GET /letters` (the page) and `POST /letter?c=<letter>[&want=b|v|
k|kh|p|f|sh|s][&strict=1]` with a 2–3 s take as the body. The student picks a letter, hears Rabbi Alouf say a word
that opens with it (`static/letters.json` + `static/letters/*.mp3`, cut from his Tehillim by `tools/make_letters.py`),
and says it — the letter with its vowel, or his word; the server trims the silence, finds the take's opening
consonant with both ears (`letters.py: onset_window`) and judges only that sound. Letters: ע ח (the throat vote:
head + classifier + Arabic ع/ح, with two measured changes for a word's start — the Arabic ear's alef is not a plain
vote there, a head that heard neither ע nor א is one), א (plain, the same ears read the other way), ק ט צ (the Arabic
ear's ق/ك, ط/ت, ص/س — heard best before a, o, u, so the student is asked to say them with "a"), ר (a rolled r as ر /
r; the Israeli r as غ), בּ/ב כּ/כ פּ/פ (b/v the phone ear's alone; k/kh and p/f with the Arabic ear), שׁ/שׂ, ת (always
t). Measured on word-initial letters (`tools/letters_study.py`, `letters_rules.py`; LAB_NOTES §27): Rabbi Alouf's
own letters called right / wrong: ע 72% / 6% (82% / 0 on clean onsets; the misses are takes where both ears first
fire on the next consonant), ח 85% / 1%, א 82% / 0, ק 85% / 1% (a/o/u), ט 84% / 6%, צ 93% / 4%, ר 88% / 2%, בּ 89% / 2%,
כּ 96% / 0, כ 89% / 3%, פּ 90% / 0, פ 92% / 0, שׁ 100% / 0, שׂ 96% / 1%, ת 84% / 1%; Israelis reading, whose ע ח ק ט צ ר
are the Israeli sounds, caught: ע 74%, ח 78%, ק 88%, ט 64%, צ 63%,
ר 30% (18% confirmed as rolled — some do roll it), and 0–5% of them called right. Two findings along the way: Rabbi
Alouf says a word-initial ב without dagesh as b (110 of 120; his vav is v), so the vet examples come from inside
words; and his ק before a sheva or i/e is heard as ك half the time — the emphasis lives in the vowel. `strict=1`
turns "not sure" into "not clearly right — work on this".
Also in v4.7: `embed.js` takes several servers (`api: [...]` or a space-separated `data-api`) and uses whichever
answers `/health` first — a home server first, the Space as the fallback; `mac/` installs the server on an
Apple-Silicon Mac as a boot-time service behind a Cloudflare Tunnel (`install.sh`, `tunnel.sh`, `update.sh`,
`bench.py`); `DK_DEVICE=mps` tries the Mac's GPU; `DK_PUBLIC=1` keeps the booth's recordings behind `DK_KEY` off the
Space too.

v4.8 (Oct 26) changes no verdict — the same takes give the same numbers, word for word — and makes what comes next
safe to measure. The word rule lives in `rule.py` (numpy only), which the server, the exams and the tests import; the
page's and the embed's JavaScript copies are checked against it on every push (`.github/workflows/checks.yml`: the
pages' scripts parse, `tools/t_parity.py` on 1,737 exam lines, `tools/review/fuzz3.py`, and `tools/rule_baseline.py`,
which replays every committed exam row and fails when any tally moves; `--update` when a change is meant). The tools
run from this repo (no `../space`). `/health` says what is running (`build`: the commit — from `BUILD_COMMIT`, which
the Dockerfile writes from the tarball, or git —, a fingerprint of every code
file, head and classifier, the two models' revisions, the rule's hash) and whether recordings are kept (`storage`);
every check, booth take and drill item carries the same stamp. The hazzan cache key is that fingerprint (it was
`v4.1` since v4.1), so a new head re-analyses his lines; old analyses are removed at start. The booth: Skip while
recording no longer files the half-take under the next task's labels; an ע/ח task needs its yes/no; a server that
does not keep recordings says so before anyone records (kept = `/data` that this process can write, `DK_DURABLE=1` —
the default on a Mac unless the cache is in a temporary folder —, or a GitHub mirror that is working); one recording
at a time, and moving on stops it; a take's labels are mirrored at once, not after the grading, and a take saved but
not checked before a restart is checked after it (twice at most). The drill keeps the take's audio as well as its features, beside the
takes (`/data/drill` when there is `/data`), and only with the key (`/check?…&drill=…&key=`; the lab page keeps the key
from `/?key=…`); `/drill` and `/drill/export` need it too. Limits: uploads over 20 MB (`/check`), 5 MB (`/letter`),
40 MB (`/submit`) get 413, and an upload decodes to 41 s (7 s for a letter) at most; more than 40 waiting checks get
503 (`DK_JOB_MAX`), counted apart from the booth's grading (`DK_GRADE_MAX`, 200), so a booth backlog never makes the
page say "busy"; `/submit` refuses with under 1 GB free; `/ref` analyses at most 60 s. Start-up housekeeping (old
analyses, waiting takes) runs only in the served process, not in a tool that imports `app`; `DK_SIDE=1` (the Mac's
bench) leaves the takes alone. The
lyrics fetch no longer runs on the event loop or retries on every request after a failure. Colab gets a random
`DK_KEY` and `DK_PUBLIC=1`.

Also v4.8 (Oct 30, made on main before the two lines met) adds the **strict check** — a switch under the result in the embed and on the lab page (`data-strict="1"`
or `strict: true` starts it on; the person's last choice is remembered). On a clean take every "not sure" word counts
as "not clearly right" (✕), and a "not sure" ע/ח counts as "not clearly from the throat". Rabbi Alouf's exam (his
takes checked against his own recording): wrong words caught 76% → 89%, good words marked 0 → 0.4%. That 0.4% is his
voice, not a general rate: on clean takes by other voices the committed exam rows give 4 → 18 of 86 good words marked
(about 21%: the archive's other hazzan, with instruments) and 13 → 51 of 537 (about 9.5%: Israelis reading); without
the clean-take requirement it would mark 168 of the 528 good archive words (32%; 168 of the 383 on takes the head can
hear, 44%). Hence strict only on a clean take: on an unclear one nothing is marked differently and the page asks for
a clearer take instead. Same rule in three places, checked word for word: `strict_of` (rule.py), `strictOf`
(index.html, embed.js) — `tools/t_parity.py`; the browser test `t_strict_ui.py`.
The home Mac's server runs on its GPU (`DK_DEVICE=mps`: 0.4 s a pasuk instead of 8–14 s, the same verdicts), and
`.github/workflows/watch.yml` opens a GitHub issue when it stops answering.

v4.9 (branch `next`, Shabbat Oct 30–31) adds **shva na / nah** for pointed lines (Tehillim). `shva.py` marks every
sheva the Sephardic way (start of a word, second of two, under the first of two identical letters, under a doubling
dagesh → said; after a short vowel, first of two, end of a word → silent; after a long vowel, after a meteg, after
the conjunction וּ, in a diphthong → left to the hazzan) and hears it on the phone ear: the pasuk's sounds aligned with
an optional short-vowel slot after each sheva consonant — "said" when an e-like vowel fills the slot (mass ≥ .5),
"silent" when no vowel at all reaches .15 between the two consonants. On Rabbi Alouf, perakim 41–150 (6,714 shvas;
the rules were set on perakim 1–40): a word-initial shva is heard said 78%, silent 1%; a shva after a short vowel
silent 91%, said 1%. A note ("say a short “e” after the ב (shva na) — a shva at the start of a word is said" / "no
vowel after the ר — its shva is silent") appears on a clean take where the take clearly differs from the rule and the
hazzan does not contradict it, or from the hazzan's own clear reading under the other rules. Tested on 243 held-out
pesukim (`tools/shva_eval.py`): 1% of his own correct shvas get a note (3% of pesukim), a short vowel put into a
silent shva is caught 69%, a shva na with its vowel cut out 36–45% (a crude stand-in for a real swallowed shva).
Also: a nikud vowel note is dropped where the hazzan is heard singing the vowel the same way (the vowel ear hears some
of his kubutz/holam as each other: 23:2's מְנֻחוֹת no longer gets "oh for oo"); ע/ח/ת notes end with "practice ע ›"
(`/letters?c=ע`, the embed's `letters` option); the booth has a list `shva` (8 short recordings) scored by `/score`.

v5.0 (Oct 31) takes one idea from each tool we studied (Tarteel, Fahm, Qara'a, Tilawa, Kriah Listener, Iqra'Eval):
- **What to check** (Tarteel's tashkeel switch): "Notes on: letters ע ח ת / vowels & shva" under the result; `notes`
  (`words` | `letters` | `all`) in `mount` / `data-notes` sets the start.
- **Hide a wrong note** (Tarteel): each note has ×; hiding one offers "send this recording, with the note you hid?" —
  with a yes, `POST /feedback` keeps the take, the hidden note and the server stamp (listed at `/feedback?key=`).
- **Ask a hazzan** (Qara'a): sends the take and a question to `POST /review`; the hazzan answers on `/hazzan?key=…`;
  the person's browser keeps the id and a token and shows the answer at the top of the checker.
- **The hazzan, then you** (Fahm's side by side): one button plays his line, then the take.
- **Tries on this line** (Tarteel/Tilawa): the last five scores, kept in the browser.
- **The voice card** (Kriah Listener): read Tehillim 23:1–2 once; the vowel confusions the ear makes on that voice —
  only kubutz/holam (U↔O) and hiriq/tsere (I↔E), never a dikduk mistake — are sent as `vc=` and those notes are left
  out (Rabbi Alouf's own 23:1–2 gives `U>O`: his מְנֻחוֹת).
- **Live follow-along** (Tarteel): `POST /follow` (the take so far → words reached, CTC path free to end anywhere);
  the line's words light up while recording, only on a fast server (`/health` device mps/cuda) or with `follow: true`.
- **Report card** (Iqra'Eval): `/report?key=` sums the booth's graded takes per kind of planted mistake and per person.
Older servers: the new embed hides "Ask a hazzan" and the send-it prompt (no `reviews` in `/health`) and never follows.

v5.1 (Oct 31, server only): on a pointed line, a "the hazzan says otherwise" vowel note is dropped when the student
said the vowel the nikud writes (the mirror of v4.9's rule). Found by testing on readers the checker never heard
(`tools/voice_register.py` aligns a new reader's Tehillim, one file per perek or one file for the whole book;
`tools/exam_voice.py` checks every pasuk against Rabbi Alouf's as the site does; LAB_NOTES §31).

v5.2 (Nov 1) fixes what an audit of v4.8–v5.1 found; no word verdict is meant to move, and the notes change only
where a fix below says so.
- **For the person checking**: in strict mode a word strict newly marks ✕ keeps its letter, vowel and shva notes and
  its throat colours (they were hidden exactly on those words); `data-strict` takes `1` / `true` / `on` / `yes`, and
  the person's own last choice wins over the site's; a double tap on Record no longer opens two recorders (the mic
  stayed on and every later take was undecodable — the embed, the voice card, the lab page and the letter page); the
  embed keeps the first server listed (the Mac) when it answers `/health` within 1.5 s, instead of whichever answered
  first; the live follow-along asks less often on a long take; the booth's shva tasks need their yes/no, like ע/ח (an
  unanswered take was scored neither caught nor missed). On the server: a ת is no longer called "sav" when the s-sound
  is its neighbour's (70 ms instead of 60: Rabbi Alouf's own 121:1); a shva at the end of a line is judged only on its
  own consonant's next ~100 ms, not on a sound after the line (a false "final" note).
- **Safety**: "Ask a hazzan" and "send this recording" exist only on a server that keeps them on its own disk
  (`/health` `reviews` = `storage.takes` persistent: `/data` or `DK_DURABLE=1`; the Space without `/data` lost them at
  its next restart, and a GitHub mirror only pushes); the upload must decode to sound that is not silence or a constant level, and
  only the server's own 16 kHz wav is kept (it was the raw body: any bytes, a phone video); the notes kept this month
  and the questions waiting are capped (`DK_FEEDBACK_MAX`, `DK_REVIEW_MAX`), each sender's too (`DK_FEEDBACK_PER`,
  `DK_REVIEW_PER`), counted with nothing let in between the count and the write; a meta with `NaN` or `Infinity` is
  refused (one kept in a question made `/reviews` a 500, so `/hazzan` showed nothing); a question's audio is served as audio
  (`nosniff`); a hazzan gets a key of his own (`DK_HAZZAN_KEY`) and can remove a question; a question whose notes are
  not a list no longer blanks `/hazzan`; v5.2 pages send the meta (name, contact, question) in the `x-dk-meta` header,
  not the URL, so the access log does not keep it; a booth take must decode to sound unless the key is sent; the
  plain `/check` path, `/letter`, `/follow` and an uncached `/ref` count against `DK_JOB_MAX` like the queued checks
  (three plain checks made a page check take 40 s while `/health` said nothing was queued); at most `DK_PLAIN_MAX` plain
  ones run at once and the others wait their turn without holding a thread (40 waiting in the thread pool froze every
  route); an uncached `/ref` (the pages' prefetch: a check analyses its line itself) has its own budget
  (`DK_REF_CONC`) and is refused past it, never queued ahead of what someone tapped; `/follow` runs one at a time and
  never beside them; `/ref?emb=1` needs the key and the hazzan analyses kept are capped (`DK_REF_KEEP`, the least
  used go first); the warm-up
  analyses the hazzan's Tehillim lines with their nikud, as the pages ask for them (it filled cache entries nobody used).
- **CI** (`checks.yml`): every top-level `.py` compiles (shva.py was never compiled, and app.py imports it at start);
  `tools/t_shva_rules.py` checks `shva.shva_marks` and every branch of `shva.notes` without models; `rule_baseline.py`
  tallies the strict marks too; `fuzz3.py` fuzzes the wrong-line rule (a random rival line), strict, and the pages' own
  no-singing statement. `watch.yml` tries the Mac 4 times 45 s apart (update.sh's restart takes 1–3 minutes) and says
  honestly that GitHub runs it late, often hours apart: for a real alert use an outside monitor (UptimeRobot or the
  like) on `/health`. `tools/t_shva.py`, `t_shva_ui.py`, `t_strict_ui.py`, `t_deeplink.py` and `t_booth.py` take the
  server as an argument (`t_booth.py` also the key, and it refuses a server not on this machine unless `--real`) and run
  from a clean clone: the intact 23:2 take is `tools/take_alouf_23_2.wav`, the pasuk comes from `lyrics_tehillim.json`,
  and the demo page and the tampered takes are made by the tests.
- **Deploying**: the pages (`static/`) update by themselves — both servers serve them from GitHub main, refreshed every
  minute — and work with a 5.1 server (they read `/health`'s `version` before using a 5.2 feature). The server part
  needs `mac/update.sh` on the Mac and a Factory rebuild on the Space; until then `/health` says `version` 5.1.

Settings (environment variables) new in v5.2, beside `DK_KEY`, `DK_PUBLIC`, `DK_DURABLE`, `DK_JOB_MAX`, `DK_GRADE_MAX`:
- `DK_HAZZAN_KEY` — a key for the hazzan who answers on `/hazzan`: it opens `/reviews`, a question and its audio, the
  reply and the remove, and nothing else (`DK_KEY` opens these too, and every booth recording, the drill, the feedback
  and the report card — not a key to hand to a teacher). Unset: only `DK_KEY`.
- `DK_FEEDBACK_MAX` (default 2000) — recordings sent with a hidden note kept at most **this month**; past it
  `/feedback` answers 503 until the month turns. `DK_FEEDBACK_PER` (default 200): from one sender a month (429).
- `DK_REVIEW_MAX` (default 2000) — questions **waiting** for a hazzan at most (since v5.2 the answered ones no longer
  count; before, it was 2000 questions ever); past it `/review` answers 503. `DK_REVIEW_PER` (default 20): waiting
  from one sender (429, "… from your network …"). A sender is one address (an IPv6 one by its /64): Cloudflare's
  `cf-connecting-ip` when the request came through the Mac's tunnel, else the first `x-forwarded-for`, else the
  connection. So a class on one school Wi-Fi shares the 20 (raise it for such a class), and where no Cloudflare is in
  front (a Space) a client can forge the header: the per-sender caps are best effort, the totals are the real limit. It
  is counted in memory only (no address is written to disk; a restart forgets it).
- `DK_PLAIN_MAX` (default 4) — plain `/check`s and `/letter`s running at once; more wait their turn (they still count
  against `DK_JOB_MAX`, so past it they get 503 "busy").
- `DK_REF_CONC` (default 2) — uncached `/ref` analyses at once; more get 503 at once (the page's prefetch just skips;
  the check analyses the line itself). A `/ref` already in the cache is always answered.
- `DK_REF_KEEP` (default 50000) — hazzan analyses kept in the cache at most (~8 KB each); past it the least recently
  used are removed, down to 90%.
- The `x-dk-meta` request header (v5.2 pages, on `/submit`, `/feedback`, `/review`): the meta JSON, URI-encoded
  (`encodeURIComponent(JSON.stringify(meta))`), in place of the `?meta=` query, which older pages still send and every
  version still reads.


- `GET /` — the lab page (record on the phone, see the word-by-word result, keep a scorecard).
- `GET /letters` — the letter checker; `POST /letter?c=<letter>[&want=…][&strict=1]` with a short take as the body; `GET /letters.json`, `GET /letters/audio/<name>.mp3` — Rabbi Alouf's example words.
- `GET /health`, `GET /info`, `GET /lyrics` (the site's lyrics.json + the Tehillim perakim, with CORS).
- `GET /ref?f=<archive mp3 | tehillim-NNN.mp3>&t0=&t1=&words=<line>` — the hazzan's line, analysed and cached.
- `POST /check?words=<line>[&ref=<f>&t0=&t1=][&nikud=<pointed line>][&pid=<text id>][&job=1][&drill=throat|plain&key=]` with the audio as the body — the take.
- `GET /drill?key=`, `GET /drill/export?key=` — the throat-drill recordings kept here (features, audio, labels) for the next classifier.
- `GET /record?set=<name>`, `POST /submit`, `GET /takes?key=`, `GET /score` — the recording booth and its scoreboard.
- `GET /tehillim/audio/<file>` — a Rabbi Alouf recording (when present).

Nothing here touches the site.
