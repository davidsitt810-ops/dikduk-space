# Shabbat work log (Oct 30–31, 2026) — the dikduk checker

## Read this first (Motza'ei Shabbat)
Nothing live changed: main, the Mac and the Space are exactly as you left them. Everything is on two GitHub branches:
- **`next`** = v4.9 — shva na / nah notes for Tehillim, practice links ("practice ע ›"), the letters page opens a
  letter from a link, a booth list "shva" (8 short recordings) with scoring, and one vowel false alarm removed.
  All tests pass.
- **`next-merged`** = `next` + a branch I found in your repo from another chat (Oct 26, `claude/gracious-bardeen-ekr2df`,
  "the foundations": the word rule in one file, checks on every push, a build stamp in /health, and fixes from an
  independent review — the important one: **a tiny upload could decode to gigabytes and crash the server**, which
  matters now that your Mac is public). It was never merged into main, and it also calls itself v4.8. I merged it
  with my work and resolved the 10 conflicts; the model-free checks pass (word rule 1,737/1,737 lines, 20,000 fuzz
  cases, measured numbers unchanged), and the server tests pass on it too (shva end to end, letters, strict switch,
  shva note in the embed, letters links, the booth with a shva take scored "caught ✓").
**Your decision:** merge `next-merged` into main (recommended), or `next` alone, or neither. Merging into main makes the
pages live at once (the Mac and the Space read them from GitHub); the Mac's server code needs
`bash ~/dikduk/app/mac/update.sh`; the Space needs a Factory rebuild.

Rules kept: nothing live changes (work on the GitHub branch `next`; main, the Mac and the Space untouched),
no site, no holiday preview, no passwords/tokens.

## Friday evening
- Branch `next` made in the repo; main (what the Mac and the Space serve) is left alone.
- Checked the vowel notes first: on Rabbi Alouf's own reading they are rare false alarms (6 of 1,191 vowels and
  12 of 1,426 in the two exams), and the text already marks kamatz katan (554 times), so "kol" vs "kal" is checked.
- Practice links: a ע / ח / ת note in the result now ends with "practice ע ›", which opens the letter checker on that
  letter (`/letters?c=ע`; the embed's `letters` option can point it elsewhere or turn it off).
- Shva na / nah: wrote the Sephardic rules (shva.py) and started measuring them on all 144 perakim.
- Shva study on all of Rabbi Alouf's Tehillim (9,286 shvas, 2,335 pesukim). The ears can hear it: the rules were
  tuned on perakim 1–40 and then checked on perakim 41–150 (6,714 shvas), where under the trusted rules he is heard
  saying the short "e" 78% of the time at a word's start (1% heard as nothing; the rest unsure) and leaving a
  "short-vowel" shva silent 91% (1% heard as a vowel). The Sephardic rule "after a long vowel the shva is said" holds
  only 60% of the time in his reading (14% clearly silent), and the ga'ya (meteg) rule fails (he says it 15%) — so
  those, and וּ + shva (he says "uvderekh"), are left to the hazzan's own reading, never to the rule.
- The booth has a new list "shva" (8 short recordings of Tehillim 23:2–3: right, a shva na swallowed, a silent
  shva said as "e") so the check can be tested on David's own voice.
- The shva check, tested the way a student errs, on 243 pesukim of the 14 perakim no head was trained on:
  · his own (right) reading: 8 notes on 818 checkable shvas (1%); 3% of pesukim got one false note;
  · a shva na with its vowel cut out of the audio: caught 36–45% (the cut is crude — a real swallowed shva may be
    easier or harder to hear; this needs real recordings);
  · a short vowel put into a silent shva: caught 69%;
  · notes landing on other shvas of a tampered pasuk: 2 in 250.
  Threshold chosen: vowel = e-like mass ≥ .5; none = no vowel frame ≥ .15 between the two consonants.
- Started the vocal-separation experiment (Demucs) on the archive lines: does taking the instruments out of the
  hazzan's recording make the pizmonim checks better? Running in the background.
