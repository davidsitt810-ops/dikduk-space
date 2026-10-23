# The fit-score server on Hugging Face — what is set up, and how to update it

Space: **davidsitt/pizmonim-dikduk** (Docker, CPU basic, Public). Address: `https://davidsitt-pizmonim-dikduk.hf.space`
— the lab page; add `/try` for someone else (a hazzan, a student). Health: `/health`. Nothing here touches the site.

## How it is built (Oct 15, 2026)

- The Space itself holds only two files that matter: `Dockerfile` and `README.md` (the front matter: sdk docker,
  app_port 7860). The template's `index.html`/`style.css` and the first upload's copies of app.py etc. are inert.
- The Dockerfile installs ffmpeg, torch (cpu) and transformers, downloads the two 1.3 GB models, then **pulls
  everything else from the public GitHub repo `davidsitt810-ops/dikduk-space` (branch main)** while building:
  `app.py`, `vowels.py`, `nikud.py`, `throat_models*.json`, `lyrics_tehillim.json`, `letter_head.pt`, `full_head.pt`,
  `static/index.html`, `static/tehillim/*.mp3`. So the Space = GitHub main.
- Why: the Hugging Face web uploader in Safari fails ("Error: Load failed") on every file it routes through its
  large-file (LFS) system, which it does by file type (`*.pt`, `*.zip`, `*.bin`…), whatever the size — a 5 MB `.pt`
  failed the same way as a 10 MB one, while `.py`, `.json`, `.md`, `.html` went through. Chrome was not tested.
- The free CPU: new accounts since mid-2026 get **zero** free-CPU quota (`Quota exceeded for flavor cpu-basic …
  limit=0`, Space shows "Paused"). PRO (about $9/month) unlocked it immediately.

## Updating the server

(Oct 23: v4.3 — whole-line evidence, the booth, `/embed.js` — is on GitHub; the Space runs it after one **Factory reboot**.)

1. Change files in the GitHub repo (I push there; the repo is public, read-only for everyone else).
2. On the Space: **Settings → Factory rebuild** (a plain Restart reuses the old build). The build re-pulls GitHub
   and keeps the cached model download, so it takes a few minutes, not fifteen.
3. Check `/health`: `ears.letter_head` and `ears.vowel_head` true, `tehillim_audio` = number of mp3s present.

If a build ever fails: the App tab shows the log; the usual causes are GitHub unreachable from the builder (just
rebuild again) or a typo in app.py (I test locally before pushing).

## More Tehillim audio

`static/tehillim/` in the GitHub repo holds eight perakim of Rabbi Alouf's reading (1, 23, 117, 121, 130, 133, 134,
150; 2 MB). The other 138 renamed mp3s (`~/Downloads/Tehilim/tehillim/`, 203 MB) can go into the same folder in the
repo in a few commits; then Factory rebuild. Without them the other Tehillim lines still check words and vowels
against the nikud, there is just no hazzan to play.

## Phone

Open the address in Safari on the iPhone, tap **Record**, allow the microphone once. After 48 idle hours the Space
sleeps; the first check after that takes a minute or two (the page says "waking the server…"). The first check of a
line not yet analysed can take up to a minute on the free CPU (the hazzan's line is analysed once and kept); the
eight included perakim are analysed when the Space starts, so those answer in about 10 seconds.

## What to do on the lab page (the loop)

- Pizmon number → a line → Hear the hazzan → Record → Stop → Check it.
- Look at the marks, tap words to hear him and then you, then tell the page the truth with ✓/✕ and Save.
- Sing some lines right, some with a wrong word, one skipped, two swapped, an ע said like א, a ח said like כ.
  Keep a few seconds each.
- When you have 10–20 takes: Copy scorecard, paste it to me. The numbers in it are what I calibrate on.
- Throat drill: for a few of the words, record "from the throat" and "plain". Two seconds each. The verdict it
  shows is the machine's current guess; where it is wrong is exactly what I need to see. The recordings' features
  stay on the server (`/drill/export`) for training the next version.
