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

- `GET /` — the lab page (record on the phone, see the word-by-word result, keep a scorecard).
- `GET /health`, `GET /info`, `GET /lyrics` (the site's lyrics.json + the Tehillim perakim, with CORS).
- `GET /ref?f=<archive mp3 | tehillim-NNN.mp3>&t0=&t1=&words=<line>` — the hazzan's line, analysed and cached.
- `POST /check?words=<line>[&ref=<f>&t0=&t1=][&nikud=<pointed line>][&drill=throat|plain]` with the audio as the body — the take.
- `GET /drill`, `GET /drill/export` — the throat-drill recordings kept here (features + labels) for the next classifier.
- `GET /tehillim/audio/<file>` — a Rabbi Alouf recording (when present).

Nothing here touches the site.
