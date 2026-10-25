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
own letters called right / wrong: ע 70% / 5% (80% / 2% on clean onsets), ח 81% / 1%, א 82% / 0, ק 84% / 1% (a/o/u),
ט 84% / 6%, צ 88% / 4%, ר 82% / 2%, בּ 86% / 2%, כּ 96% / 0, כ 87% / 3%, פּ 90% / 0, פ 88% / 0, שׁ 99% / 0, שׂ 94% / 1%,
ת 84% / 1%; Israelis reading, whose ע ח ק ט צ ר are the Israeli sounds, caught: ע 74%, ח 76%, ק 89%, ט 64%, צ 63%,
ר 30% (18% confirmed as rolled — some do roll it), and 0–5% of them called right. Two findings along the way: Rabbi
Alouf says a word-initial ב without dagesh as b (110 of 120; his vav is v), so the vet examples come from inside
words; and his ק before a sheva or i/e is heard as ك half the time — the emphasis lives in the vowel. `strict=1`
turns "not sure" into "not clearly right — work on this".

- `GET /` — the lab page (record on the phone, see the word-by-word result, keep a scorecard).
- `GET /letters` — the letter checker; `POST /letter?c=<letter>[&want=…][&strict=1]` with a short take as the body; `GET /letters.json`, `GET /letters/audio/<name>.mp3` — Rabbi Alouf's example words.
- `GET /health`, `GET /info`, `GET /lyrics` (the site's lyrics.json + the Tehillim perakim, with CORS).
- `GET /ref?f=<archive mp3 | tehillim-NNN.mp3>&t0=&t1=&words=<line>` — the hazzan's line, analysed and cached.
- `POST /check?words=<line>[&ref=<f>&t0=&t1=][&nikud=<pointed line>][&drill=throat|plain]` with the audio as the body — the take.
- `GET /drill`, `GET /drill/export` — the throat-drill recordings kept here (features + labels) for the next classifier.
- `GET /tehillim/audio/<file>` — a Rabbi Alouf recording (when present).

Nothing here touches the site.
