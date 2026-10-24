# The Shabbat round (Oct 23–24, 2026) — what changed, what was measured, what to do

## The one thing to do

On the Space (huggingface.co/spaces/davidsitt/pizmonim-dikduk): **Settings → Factory rebuild**. One click, about ten
minutes. It puts the new server (v4.6: the new rule and the retrained letter head) and all 144 perakim of Rabbi
Alouf's Tehillim on the Space. The page and the embed script update themselves from GitHub, so your phone already
shows the new rule — but against the old server until the rebuild, where the new signals are simply missing.

Then the test only you can do: `https://davidsitt-pizmonim-dikduk.hf.space/record?set=david` — 20 short recordings,
about 15 minutes. Everything below was measured on hazzanim and on Israelis reading; nothing yet on a learner.

## Bugs found by testing, and fixed

1. **A wrong line was never called a wrong line.** The "This does not sound like this line" verdict was switched on
   only for a "clean" take, and a wrong line is never clean. Measured 0 of 70 wrong pesukim as a verdict (the number
   behind it was right; the gate hid it).
2. **The same verdict was wrong the other way on other voices.** 80 Israelis reading sentences (held-out FLEURS
   recordings): the old measure called 33 of 80 *right* sentences "not this line" — a voice the letter head reads
   poorly looks exactly like a wrong text to it. Rebuilt: the server now scores the text's *other* lines (the perek's
   other pesukim, the pizmon's other lines) and calls a wrong line only when another line beats the written one by a
   margin, fits the audio itself, and is heard. Rabbi Alouf's wrong pasuk: 149 of 149; his right pasuk: 0 of 150;
   the Israelis' right sentences: 0 of 80.
3. **The letter head did not know other voices.** It had been trained on Rabbi Alouf and the archive's hazzanim
   only; on Israelis reading it heard 2 of 80 takes "clean" and said "not sure" about half the words. Retrained
   overnight with 1,500 clips of Israelis reading (ע written as א and ח as כ, as they say them, so it learns the
   voices without learning that an alef sound is an ayin) and 410 Egyptian Arabic clips (ع ח from the throat, so it
   keeps hearing the throat in voices it does not know): clean takes 2 → 15 of 80, "not sure" 32 → 21%, swapped
   words caught 37 → 75%, the wrong sentence called 23 → 60 of 78 — and Rabbi Alouf unchanged to the word.
4. **The pizmonim case had a 9% false-alarm rate on correct words.** The archive's own second recordings (another
   hazzan, instruments) against the site's reference: a right word went red 8.6% of the time, because on a poorly
   heard take the rule trusted the phone recognizer twice and never asked the letter head. Now 2% — and what is left
   is words the singers do not sing as written (the same words red in two independent recordings).
5. **A skipped word was reported as "swapped" with its neighbour** (a missing word also "gains" a little from a swap),
   so the correctly sung neighbour went red too. Fixed by comparing the two gains.
6. **One wrong word in a short line switched the clever evidence off**: the "clean" gate took the median letter-head
   score over the line's words, which a single wrong word pulls under the bar in a 3–5-word line. The median now
   leaves the lowest word out and takes the true median (an independent review's catch: one well-heard word no
   longer makes a short line "clean").
7. **Silence or noise** came out as "not this line" with every word red; now: "I did not hear any singing".
8. **The booth's scoreboard** collapsed a repeated word (קדוש קדוש קדוש) into one, matched words by their spelling
   with final letters, judged the letters of a word that was not there, and fell over on one broken record.
9. **A Tehillim perek without audio on the server** got a live play button and a failed hazzan request; the page now
   asks the server which perakim it has.
10. Vowel notes and "plain" ע/ח verdicts appeared on takes the ears could not hear properly (another voice with
    instruments: 117 vowel notes on 528 right words, 9 plain verdicts, all on such takes); both now need a clean take.

## Numbers (before = Friday morning's v4.3; after = v4.6)

| | right words red | skipped caught | swapped caught | replaced caught | wrong pasuk/line (verdict) |
|---|---|---|---|---|---|
| Rabbi Alouf, 70 held-out pesukim | 0 / 1,850 → **0** | 97% → 97% | 92% → 96% | 79% → 76% | 0/70 → **70/70** |
| Rabbi Alouf, 80 fresh pesukim (never used for tuning) | **0 / 2,290** | 98% | 99% | 71% | **79/79** |
| 80 Israelis reading, no hazzan | 2.4%* → 1.3%* | 50% → 46% | 39% → 75% | – | 33/80 *right* ones called wrong → **0**; wrong ones caught 60/78 |
| Pizmonim archive, another hazzan with instruments, 87 takes | 8.6% → 2.0% | 50% → 27% | 40% → 50% | – | 4/76 → 11/98 |

\* on the Israelis, most of the red words are the dataset's own faults — clips whose audio stops before the transcript
ends, English words and numbers in the transcript; on clean-transcript sentences it is about 4 words in 1,000.

Throat letters, Rabbi Alouf's 150 intact pesukim: ע from the throat 84–90%, "not sure" 10–15%, wrongly "plain" 1 of
188; ח from the throat 90–99%. Israelis (who say ע like א and ח like כ): ח plain 90%, ע plain 69% / not sure 28% /
"throat" 2%. Vowel notes against the nikud on his reading: 0.5–0.8% of slots.

Three copies of the rule — server, page, embed — agree word for word on 1,500 recorded lines and 240,000 synthetic
ones (`tools/t_parity.py`; the review's fuzz under `tools/review/`).

## What is still true, and what I need

- **Nothing is measured on a learner's voice.** The Israelis are the nearest thing; your 20 recordings are the one
  calibration that matters, and the scoreboard now says per take whether the ears heard it cleanly.
- A replaced word that resembles the original (באדני for אדני) still passes or stays "not sure" (70–77% caught).
- One-consonant words (את, רעה) are never red on their own — the evidence cannot separate them safely.
- Pizmonim sung with instruments: half the words come out "not sure", a quarter of the takes "I could not make out
  the words". A student singing a cappella into a phone should fare much better; the booth will show.
- The archive test's ground truth is the site's sync events; a few lines are plainly sung with other words than the
  site's text, and at least one clip holds the next line.
- Two settings are yours to type when you want them: the Space secret `DK_KEY` (so I can read the booth's
  recordings from here) and a GitHub token for the recordings mirror (`GH_TOKEN`).

Everything is in GitHub (`davidsitt810-ops/dikduk-space`; `tools/` has every exam, its rows and the training
scripts) and in `~/Downloads/dikduk-v4/` on the Mac; `LAB_NOTES.md` §23–26 has the measurements in full.
