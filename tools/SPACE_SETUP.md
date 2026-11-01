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

## Before the next rebuild (v4.8): keep the recordings

A rebuild, a restart or the 48-hour sleep empties the Space's `/tmp`, and that is where the booth's takes and the
throat drill live unless the Space has storage. In this order:

1. Save what is there now: open `/drill/export` (v4.6/v4.7 serve it without a key) and keep the file.
2. Space → Settings: attach persistent storage (a private Storage Bucket mounted at `/data`, read-write). The server
   tries a test file there at start and uses `/data/takes` and `/data/drill` only if it can write.
3. Space → Settings → Secrets: `DK_KEY` (any long random string: it opens `/takes`, `/drill`, the scoreboard, and lets
   the lab page keep drill takes — open the lab page once as `/?key=<it>`), and `GH_TOKEN` for a second copy in the
   private `dikduk-recordings` repo (fine-grained token, Contents: read and write, that one repo).
4. Optional, once: replace the Space's own `Dockerfile` with the repo's (a text file: the web uploader takes it). Only
   the new one writes `BUILD_COMMIT`, so `/health` can name the commit; without it `build.commit` is null and the
   `build.files` fingerprints still say exactly which code and heads run.
5. Factory rebuild. Then `/health`: `version` 4.8, `build.commit` = the commit on GitHub main (with step 4),
   `storage.durable` true. If `storage.takes` says `temporary` with storage attached, the mount is not writable for
   the app: the booth warns people before they record.

## v5.2: "Ask a hazzan" and "send this recording" need the storage too

The questions to a hazzan (`/review`) and the recordings sent with a hidden note (`/feedback`) are kept beside the
booth's takes. Without storage at `/data` (`storage.takes` says `temporary`) from v5.2 the server turns both off:
`/health` says `reviews` false, the embed hides the two buttons, and a direct POST gets 503 ("questions are not kept
on this server"). They were lost at the next restart or sleep before. A `GH_TOKEN` mirror does not count here: it
only pushes, so after a restart the questions would be on GitHub but not on the server's `/hazzan`. To have them
on the Space, attach the `/data` storage above and Factory rebuild; the Mac keeps them on its own disk. The hazzan who
answers on `/hazzan` can have a key of his own, `DK_HAZZAN_KEY` (a Space secret): it opens the questions and nothing
else, where `DK_KEY` also opens every booth recording.

## Updating the server

(Oct 23: v4.3 — whole-line evidence, the booth, `/embed.js` — is on GitHub; the Space runs it after one **Factory reboot**.)

1. Change files in the GitHub repo (I push there; the repo is public, read-only for everyone else).
2. On the Space: **Settings → Factory rebuild** (a plain Restart reuses the old build). The build re-pulls GitHub
   and keeps the cached model download, so it takes a few minutes, not fifteen.
3. Check `/health`: `ears.letter_head` and `ears.vowel_head` true, `tehillim_audio` = number of mp3s present.

If a build ever fails: the App tab shows the log; the usual causes are GitHub unreachable from the builder (just
rebuild again) or a typo in app.py (I test locally before pushing).

## More Tehillim audio

(Oct 23) `static/tehillim/` in the GitHub repo now holds all 144 perakim of Rabbi Alouf's reading that David's
download had (16 kHz mono 48 kbps, 102 MB; the same timeline as the sync events in `lyrics_tehillim.json`). The six
perakim he did not record (69, 87, 89, 104, 120, 139) are text-only: words and vowels are checked against the nikud,
there is just no hazzan to play. The Space gets the files at the next Factory rebuild.

## Phone

Open the address in Safari on the iPhone, tap **Record**, allow the microphone once. After 48 idle hours the Space
sleeps; the first check after that takes a minute or two (the page says "waking the server…"). The first check of a
line not yet analysed can take up to a minute on the free CPU (the hazzan's line is analysed once and kept); the
eight most-used perakim (1, 23, 117, 121, 130, 133, 134, 150) are analysed when the Space starts, so those answer
in about 10 seconds; any other pasuk is analysed the first time someone picks it (the page fetches it while you record).

## What to do on the lab page (the loop)

- Pizmon number → a line → Hear the hazzan → Record → Stop → Check it.
- Look at the marks, tap words to hear him and then you, then tell the page the truth with ✓/✕ and Save.
- Sing some lines right, some with a wrong word, one skipped, two swapped, an ע said like א, a ח said like כ.
  Keep a few seconds each.
- When you have 10–20 takes: Copy scorecard, paste it to me. The numbers in it are what I calibrate on.
- Throat drill: for a few of the words, record "from the throat" and "plain". Two seconds each. The verdict it
  shows is the machine's current guess; where it is wrong is exactly what I need to see. The recordings' features
  stay on the server (`/drill/export`) for training the next version.
