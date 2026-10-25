# Dikduk checker — lab notes, night of Oct 12–13

Everything here was measured, not assumed. Where I am unsure I say so.

## 1. Why the old words check flip-flopped

Measured through the live `/api/asr` (Whisper on Cloudflare), from the preview's origin, on Moshe Dwek's own
recording of 319 (`md cd08 15.mp3`, line 1 = 0.35–6.9 s). 30 calls, nothing deployed.

| Input | Whisper wrote |
|---|---|
| hazzan's line 1, with the line as hint, **10 tries** | `מעזי אז כלה קץ עזבי למה` — identical 10/10 |
| same, **no hint**, 4 tries | `מה עוזי אזכה לקיס עוז בלמה` — identical 4/4 (old matcher: 1 of 6 words "right") |
| same, hint = **line 2's** words | `מי עשה לך עשה לך עשה בלמה` — 4 hint words nobody sang |
| עזבי **cut out** of the audio, with hint | `מעוזי אז כלה קצת למה` — caught |
| אז / כלה **swapped** in the audio, with hint | `מעזי אז כלה קץ עזבי למה` — **missed** |
| real audio, hint says כלב for כלה | wrote **כלב** |
| real audio, hint says שובי for עזבי | wrote **שובי** |

So: Whisper on the same bytes is stable (confidence numbers moved by 0.01, so these were real re-runs, not a
cache; fairly sure, not certain). The hint makes Whisper write the hint, so a wrong word that sounds anything like
the right one passes; without the hint Whisper mishears correct singing. Each of David's tries was a new take
(David confirmed), and Whisper, unsure on singing, tipped differently between "copy the hint" and "write what I
hear". The log's Oct 9 claim "a hint does not make Whisper write words that were not sung" is wrong (row 3).
Whisper writes dictionary spelling, so it can never hear ע vs א.

## 2. The new design (David chose "fit score on a small server")

One model, `facebook/wav2vec2-xlsr-53-espeak-cv-ft` (a phone recognizer, IPA, 20 ms frames; its alphabet has
ʕ ħ ʔ h x χ). No Whisper, no hint, no 60/hour limit, deterministic. For any audio:

1. phone log-probabilities (one model run);
2. each word's **consonant skeleton** (Sephardic; a letter with several possible sounds is given all of them at
   once: ב b/v, כ k/x/χ, פ p/f, ש ʃ/s, צ ts/s, ח ħ/h/x/χ, ק k/q, ר r/ɾ/ʁ, ת t/θ, ג ɡ/ɣ, ד d/ð; א ע י ו left out;
   ה only inside a word) force-aligned on the probabilities (CTC Viterbi, checked equal to torchaudio's
   `forced_align` on random data): every consonant gets a time and a probability, and which sound was found;
3. word spans from the consonant spans;
4. the phones heard inside each word; for each ע/ח the window where it must have been said.

The hazzan's archive line goes through the same steps (`/ref`, cached on the server); his phones per word become
the expected sounds, force-aligned onto the take → **fit** per word. The take's own skeleton gives **skel** per
word. Nothing from a dictionary: the yardstick is the hazzan.

Files: `dikduk-space.zip` = `app.py` (server + the rules above, commented), `Dockerfile`, `README.md`,
`static/index.html` (the lab page, served by the server at `/` so the phone's microphone works). Tests in
`space_test/`: `t_plumbing.py` (random weights: alignment vs torchaudio, routes), `t_page.py` (page render, mocked
server), `t_live.py` (real page + real server + real m4a take), `eval_archive.py` (calibration).

## 3. What the measurements say

**Same singer (Dwek 319 line 1, model in the browser, q4f16):** self-fit .62–.94; עזבי cut out → .00; אז/כלה
swapped → אז .00; line 2's audio checked as line 1 → .00–.37.

**Other singers, same lines (real server, fp32), clean recordings:** 200 Shrem line 3 vs Dodi: skel/fit
והעדה .92/.70, לחובי .90/.63, בטבעו .64/.56, בים .37/.01 (one consonant, "yam"); לחובי cut out → .34/.02;
לחובי/בטבעו swapped → fit .31/.39 (skel unchanged: skel is order-blind inside the line); לחובי replaced by
another word → .49/.38. 200 Shrem line 2 vs Dodi: .91/.34 .67/.13 .91/.53; אשוב cut out → .00/.00.
42 Archives line 3 vs MKairey: fine except האיש .06 and הלך .08 as sung (an opening ה is barely voiced in
singing; opening ה now left out of the skeleton).

**Archive-wide (3 pizmonim, 14 takes by other hazzanim, 145 word rows; `eval_archive.py`):** medians right vs
wrong: skel .49 vs .23, fit .30 vs .11 (words with ≥2 consonants). No single threshold separates words cleanly:
flagging skel<.2 wrongly flags 16% of right words and catches 47% of wrong ones. Reasons seen in the rows: the
archive takes with instruments (Sayegh, Menaged) score ~.3 even when right; the sync times are coarse (a clip
can hold a line twice); the "wrong" test reuses words the lines share; one-consonant words are unconstrained.
Line-level means separate much better on clean recordings (right .5–.83, wrong .12–.43).

**ע and ח, honestly:** on Dwek's sung ayins the model gives ʕ at most .17 and usually nothing (the ayin melts
into the vowel). Four hazzanim's ח all come out as **h** (never x), so a ח said like כ should show as x/χ, a real
signal to test on David. For ע this model's phone head is not enough; the lab page's **throat drill** records
short paired words and saves the model's hidden-state embedding (layer 16) with each, so a small classifier
(throat vs plain) can be trained on David's own voice plus the hazzanim as positives.

## 4. The rule shipped in the lab page (first version, to be calibrated on David's takes)

- word with ≥2 consonants: **off** (red) when skel < .20 and fit < .15; **unsure** (yellow) when skel < .40 or
  fit < .20; else **ok**.
- one consonant: never red alone; unsure below .20.
- the sentence names red words ("X was not heard where it belongs") and yellow ones ("Not sure about X: tap to
  hear him, then you"). Tapping a word plays the hazzan's word, then yours.
- ח: reported from the aligned consonant (ħ / h / x / χ and their masses). ע: reported from its window, not judged.
- Your verdict row (✓/✕ per word) + Save → the scorecard (on the phone), Copy → paste it into the chat.

## 5. What a clean phone take should look like

Dwek's studio line scored .94–.99 on skel. David singing alone, close to the phone, should look more like that
than like the archive's accompanied takes. That is the first thing the scorecard will tell us.

## 6. Open points

1. The server needs a home. Prepared for a free Hugging Face Space (CPU, Docker). I cannot create the account or
   the Space; steps are in `SPACE_SETUP.md`. A free Space sleeps after 48 h idle and takes ~1–2 min to wake.
   Build time ~10 min (the model downloads while building). Check: ~3–6 s per take.
2. Line times for the hazzan come from the site's sync events (deciseconds); for 319 Dwek the hand-set phrase
   times are used. Coarse times make the reference worse. Later: take the reference from the sync'd words.
3. Vowels are not judged at all yet (no nikud in the lyrics). A hazzan-vs-you vowel comparison is possible with
   the same phones once the words check is trusted.
4. The old `pzdk.js` / `slHear` path is replaced entirely; plugging in = one POST to `/check` from `sline.js`
   with the line's words and the hazzan file + times (handoff note comes when David says it's perfect).

---

# Night 2 (1:00–2:10 AM): David chose "all the way". Two free experiments, both run on the archive.

## 7. Experiment A: an Arabic-LETTER ear (no language model)

Whisper's Arabic mode failed because its language model wrote the Arabic words it knows. A CTC letter model
(`jonatasgrosman/wav2vec2-large-xlsr-53-arabic`) has no such pull. On Dwek's 319 it wrote, line 1:
`مَع عُزِّي أز كالى عكيصعازِب لاما` — ع at both ayins; line 2: `عَنمِي عا سَيعوت ليَتابا وُوانحَاما` — ع at עמי, **ح** at
the ח of ונחמה; line 5: ع at מעזי, דמעי and both על. md cd03's ח also → ح.

Measured archive-wide (44 pizmonim, best recordings, 4 lines each; `exp_arabic3.py`, the ear used as an aligner
with letter alternatives, ע and א both offered {ع, ا, أ, ء}): a hazzan's **ע comes out ع 45%** of the time, an
**א 16%**; **ח → ح 43% / خ 29% / ه 28%**; **כ → ك 61% / خ 39%, never ح**; ה → ه 100%. So "ع heard" is good
evidence of a throat ayin and ح of a throat het; "not heard" is not evidence of a plain one (archive quality,
coarse windows).

## 8. Experiment B: throat classifiers on the phone model's hidden features

1,398 letter windows (ע 207, א 375, ה 342, ח 184, כ 290) from 316 lines of 57 best recordings; features = mean
and max of hidden layers 6/10/14/18/22/24 over the window; logistic regression; cross-validation holding out
whole recordings AND never letting a word appear on both sides (`exp_throat.py`, `exp_throat_fit.py`):

| task | phone head alone | best layer | AUC |
|---|---|---|---|
| ח vs ה | .77 | 6–24 (mean+max) | **.96–.97** |
| ח vs כ | .78 | 6 (mean+max) | **.94** |
| ע vs א | .61 (ʕ) | 10 (mean+max) | **.73** |

The throat het is clearly in the features. The ayin is only partly there with these loose windows.

## 9. Server v2 (in `dikduk-space.zip`): two ears + two classifiers

Each ע/ח now gets: the classifier's probability, the Arabic ear's window peaks and aligned winner, and a verdict
**throat / plain / unsure** (rules in `app.py`, `throat_probe`). Both ears must agree for "throat"; "plain"
needs a plain onset actually heard, not just a throat missed (a hazzan's weak ע in בטבעו would otherwise be
called plain).

Checks on the real server, real audio:
- **Dwek 319, 8 ayins:** 6 throat, 2 unsure, 0 plain. His ח: throat (classifier 1.00, ear ح 1.00).
- **Israeli read speech (FLEURS he_il, 40 sentences, ע said like א, ח like כ):** ע → plain 57%, unsure 35%,
  **throat 8%** (6 of 79; the false-alarm rate to beat); ח → plain 72%, unsure 28%, **throat 0%**.
- Same speech, words check on right words (≥2 consonants): median skel **.86**, below .2 only **4%** — clean,
  close-mic input behaves far better than archive clips. That is the regime your phone takes are in.
- Other hazzanim: Shrem's and Dodi's ח in לחובי → throat; their ע in בטבעו → unsure (was "plain" before the fix).
- Time per take with both ears: ~6–10 s on 2 CPUs.

## 10. The "all the way" plan (what training on the archive means)

Target: a model raised on Aleppo singing instead of guessing at it.
1. **Data** (free): every synced line of every recording with words (1,121 recordings, 445 pizmonim ≈ 10+
   hours), text = the Hebrew letters of the line. Hazzanim pronounce correctly, so ע and ח are separate target
   letters the model must learn to hear; vowels stay implicit (no nikud).
2. **Model**: fine-tune the phone model (or the Arabic one) with a Hebrew-LETTER output head on that data — a few
   hours on one rented GPU (T4/A10, ~$0.5–1/h), on the same Hugging Face account (a GPU Space or a job). I write
   the training script and the evaluation; you create the account and press start.
3. **Negatives**: Israeli speech (FLEURS, Common Voice) for "ע said like א / ח like כ", and your drill
   recordings; both ears' errors on these are the exam.
4. **What can go wrong**: the sync times are coarse (lines sung twice, stray words) — alignment must be cleaned
   first (the server's own aligner can do that); accompanied recordings must be filtered (the site already
   measures voice-above-noise); and if hazzanim's sung ayin truly melts into the vowel, the trained model will
   say "unsure" there too — that is a fact about singing, not a bug, and the lab page will show it.
5. **Vowels**: after the words check is trusted, compare your vowels to the hazzan's with the same phones;
   or add a nakdan (automatic nikud) to get expected vowels.

---

# Day 2 afternoon (12:50–3:10 PM): "do whatever makes it better"

## 11. A model raised on the archive, the CPU version (server v3's third ear)

The sandbox turned out to reach Hugging Face, so the archive training started here instead of waiting for a GPU:
- **Extraction** (`extract_lines.py`): 1,550 synced lines (the best recording of each pizmon, up to 8 lines) plus
  119 Israeli sentences, through the Arabic-letter model: hidden layers 12 and 18 and the line's Hebrew letters
  force-aligned on its letter probabilities (ע and א both offered {ع ا أ ء}). 2.8 GB of features. Lines whose
  alignment is poor (instruments, talk, a wrong sync) are filtered by their own alignment score; 1,024 lines kept.
- **The head** (`train_head.py`, `letter_head.pt`, 10 MB): three temporal-convolution layers on the frozen hidden
  layer 12, CTC-trained with the lines' Hebrew letters as targets (22 letters + space); 10 epochs, 11 minutes on
  two CPU cores. It outputs Hebrew-letter probabilities per 20 ms frame; the line's letters are aligned on them with
  ע/א and ח/כ as alternatives and the letter with the mass wins.
- **Exam, 21 pizmonim it never saw:** letter error rate 37% (greedy, no language model — fine for an aligner).
  **Hazzan ע heard as ע 80%** (n=75), hazzan א as א 81%; **ח as ח 94%**, כ as כ 80%. **Israeli ע (said like א) heard
  as ע 28%**, Israeli ח (said like כ) as ח 33%. For comparison the Arabic ear alone: ע→ع 45%, א→ع 16%.
- A second training with the Israeli sentences added (relabeled ע→א, ח→כ, as they are said) did not converge in two
  tries (loss stuck ~3 vs .5; letter error 70%) and was discarded; the archive-only head is the one shipped. Worth
  retrying with more data and a longer schedule.

## 12. Ayin classifier v2 (`train_ayin.py`, `throat_models_v2.json`)

On the Arabic model's hidden layer 12, windows = the letter's own aligned frames ±4 (80 ms), 931 hazzan ayins vs
1,386 hazzan alefs, plus Israeli ayins as extra negatives (what a plain ayin sounds like): held-out recordings and
words AUC .75, catches 65% of hazzan ayins at .5 while calling 4% of Israeli ayins "throat" (42% without the
Israeli negatives). For ח the v1 classifier (phone model, AUC .94–.97) stays primary.

## 13. The three-ear vote (server v3, `throat_probe` in `app.py`)

Each ע/ח: the head (mass ratio ≥ .7 throat / ≤ .3 plain, only where it put real mass), the classifier (ע: v2 ≥ .6 /
≤ .3; ח: v1 ≥ .7 / ≤ .3), the Arabic ear (ع or ح heard with peak ≥ .3 / a plain onset actually heard). "From the
throat" = two votes for and none against; "plain" the same the other way; else "not sure".

Measured on the real server:
| set | ע throat | ע unsure | ע plain | ח throat | ח unsure | ח plain |
|---|---|---|---|---|---|---|
| Dwek 319, lines 1, 2, 5 | **8/8** | 0 | 0 | 1/1 | 0 | 0 |
| four other hazzanim, recordings not in training (Shrem, Archives, md cd03, Sayegh) | **16/21** | 3 | 2 | 7/8 | 1 | 0 |
| Israeli read speech, 40 fresh sentences no model saw (ע said like א, ח like כ) | **0/48** | 21 | 27 | **0/77** | 27 | 50 |

So: a hazzan's throat letter is called "from the throat" about 3 times in 4 and never "plain" on the clean
recordings; a plain-said ע or ח is never called "from the throat". The two "plain" calls on hazzanim (Shrem's והעדה,
Sayegh's עלת) are either soft ayins or the checker's mistakes — I can't tell by ear; your ear decides.

## 14. Also today
- Word spans no longer swallow the clip's edges: the first word starts a little before its first consonant, the last
  ends a little after its last one (a line sung twice, an announcement, or silence no longer lands in a word).
- The head's own per-word letter score (`hskel`) is shown as a third number per word; on the noisy archive set it
  separates right from wrong words about as well as the IPA skeleton, so skel + fit stay the rule.
- Clean read speech, right words: only 2–4% below the red line (`exp_israeli*.py`) — your phone takes live here.
- Time per take with three ears: ~8–12 s on two CPU cores (the Space's free tier). A paid CPU would halve it.

## 15. Honest standing after day 2
words **7/10** (the yellow "not sure" zone is where the calibration from your takes goes), **ח 8.5/10**,
**ע 7/10** (up from 5: hears the hazzanim's ayin 3 times in 4, never accuses an Israeli-style one of being
throaty; your own voice is the open question), vowels **0/10**. Next lifts, in order: your takes and drills (the
page keeps them with features), a bigger head on all 3,000 lines (extraction continues), the GPU fine-tune of the
whole model on the archive (the plan in section 10).

## 16. Day 2 evening (5 PM): the head grown to 3,000 lines (server v3.1, the package now sent)

Extraction finished at 3,000 archive lines (1,944 kept after the quality filter). Training a fresh head on them
got stuck twice in the "all blank" trap that CTC training is known for; warm-starting from the 1,550-line head
and continuing 6 epochs at a lower learning rate worked:

| held-out pizmonim | 1,550-line head | 3,000-line head |
|---|---|---|
| letter error rate | 37% | **24%** |
| hazzan ע heard as ע / א as א | 80% / 81% | **86% / 87%** |
| hazzan ח heard as ח / כ as כ | 94% / 80% | **96% / 97%** |
| Israeli ע (said like א) still heard as ע | 28% | **21%** |
| Israeli ח (said like כ) still heard as ח | 33% | **28%** |

(The held-out set of the second run may overlap the first run's training pizmonim, so its hazzan numbers are a
little optimistic; the Israeli numbers are clean.) The v2 classifiers were refit on the same 3,000 lines (4,748
ayin/alef windows; AUC .76).

Three-ear vote, re-measured: fresh Israeli sentences, ע called throat **1 of 48**, ח **0 of 77**; the
accompanied/noisy third recordings of 200, 42, 1, 319 (Sayegh and Menaged "with instruments", BTB): ע 11 throat /
9 unsure / 2 plain, ח 3 throat / 9 unsure / 0 plain — on noisy input it mostly says "not sure", which is the right
failure. Also new: a ת said like samekh (the Ashkenazi sav) is offered to the aligner and reported when it wins
clearly.

# Night 3 (Oct 13, 5 PM – 11 PM): Rabbi Alouf's Tehillim (server v4)

## 17. What was done with the 146 files

**Alignment.** Every perek (144 of 150; 69, 87, 89, 104, 120, 139 are not in the folder) was decoded, run through
both models in 20-second windows (stitched), and its Masoretic text (Sefaria, "Miqra according to the Masorah",
qere in the text) force-aligned on the phone model — every consonant AND every vowel offered the sounds it may be
in Sephardic reading (`tehillim/nikud.py`: dagesh decides b/v k/x p/f, sin dot, furtive patah, matres, the Name read
אדני, kamatz katan = o). Long perakim use a banded Viterbi (`tehillim/ctcutil.py`; perek 119 = 17 minutes, 5,993
units, all placed, mean certainty .80). Result: 293 minutes, 97,305 sounds placed, mean certainty .795, no perek
below .6 — his reading is that clean. Pasuk and word times from this feed the site package and the lab page.
"Lechu Neranena" = Tehillim 95:1–3 (fit .83); "151 Mi Yiten Mi_sion" = 14:7 sung slowly (fit .68).

**His register** (`alouf_register.md`): the Arabic ear hears a pharyngeal ع in **83%** of his ayins (start of a word
91%, middle 83%, end of a word 47%; after ר 56%, after ש 67%) and ع in only 13% of his alefs; his ח is ح **99%**
(a כ never). ת always t, ד always d, ג without dagesh 81% g / 19% gh, צ = the emphatic ص (71%) rather than ts,
ק = uvular ق 88%, ר a front r, consonantal ו = v. NOT findings: ב/כ/פ and the vowel classes were dictated by the
nikud in the alignment, so the register does not test them; the vowel head's exam does (below). The 40
worst-fitting words (listed in the register) are the places to listen for a misread or a skipped word.

**Training.** 2,364 pesukim became training items (the Arabic model's layer 12 + its letter alignment, like the
archive lines), with 14 perakim (243 pesukim) held out and never seen by the heads.

| held out | letter head v3.1 (archive only) | **letter head v4** (archive + Alouf ×2, 4 epochs warm) |
|---|---|---|
| hazzan lines: ע→ע / א→א | 86% / 87% | 85% / 87% |
| hazzan lines: ח→ח / כ→כ | 96% / 97% | 93% / 96% |
| Alouf pesukim: ע→ע / א→א | – | **99% / 99%** |
| Alouf pesukim: ח→ח / כ→כ | – | **100% / 100%** |
| Israeli ע still heard as ע / ח as ח | 21% / 28% | **24% / 11%** |

So the head learned Rabbi Alouf nearly perfectly and kept what it knew about the hazzanim (the 3-letter drop on
ח is 3 letters of 104). Throat classifier v3 (`train_ayin2.py`, his ע/ח against his own א/כ/ה, same voice both
sides, plus the Israeli negatives): held-out Alouf ע caught 96% with 3% false alarms on his alef, ח 99% / 1%;
hazzan ע 70% / א 25% (unchanged: the archive labels are letters, not verified pronunciation); Israeli ע called
throat 10%, ח 2%. Cross-validated AUC .95 (ע) and .98 (ח), from .76 / .90.

**The Arabic ear's vote, changed.** Measured on ±4-frame windows: the ع PEAK is ≥ .5 for 82% of his ayins, 4% of his
alefs, 12% of Israeli ayins, 6% of Israeli alefs (hazzanim: 53% / 12%); the ح peak ≥ .5 for 98% of his hets, 0% of כ,
1% of ה, 0% of Israeli ח. The old rule also demanded that ع WIN the aligned frames against alef, which threw away
clear peaks (Alouf's רעי: ع .81 but "heard ا"). v4 votes "throat" on the peak alone (≥ .5); the "plain" rule is unchanged.

**The vowel ear (new, `full_head.pt` + `vowels.py`).** Same head shape, warm-started from the letter head, trained
on Alouf only with letters + the vowel classes A E I O U (from the nikud) as targets, 8 epochs. On the held-out
perakim, with each vowel offered all five classes: A 100%, E 99%, I 99%, O 100%, U 99% right. As the server uses it
(the line without nikud aligned as letter [vowel?] letter [vowel?] …, ו י א optional, and the vowels found compared
with the nikud position by position): the vowel count matched the nikud in 94% of words, 4,096 "clear" slots of
which 100% right, and **17 of 1,978 words flagged = 0.9% false alarms on a correct reader** (listed by
`vowel_flags.py`; several are real subtleties — a furtive patah, a final shuruk sung as o — not ear errors).
Through the whole server (`eval_vote_v4.py`, 40 held-out pesukim cut from the mp3): 1.9% of words flagged.
Caveat that matters: this is ONE voice, read speech. On sung pizmonim the same ear scores both the hazzan and the
student, and only clear disagreements are shown, but I have no measurement there until your takes — so the panel
says so and does not change a word's ✓/✕.

**The whole v4 server, measured** (`eval_vote_v4.py`, `eval_hazzan_v4.py`, `exp_israeli_fresh.py`):
| set | ע throat / unsure / plain | ח throat / unsure / plain | words red (right words) |
|---|---|---|---|
| Rabbi Alouf, 40 held-out pesukim | **43 / 6 / 0** | **43 / 1 / 0** | 0 of 318 (10 unsure) |
| 30 held-out hazzan lines (24 recordings, accompanied, site sync times) | 13 / 10 / 1 | 14 / 6 / 0 | 7 of 142 |
| 40 fresh Israeli sentences (ע like א, ח like כ) | **1 / 24 / 23** | **0 / 19 / 58** | 2% below .2 |

**Also in v4:** the Name is read אדני by every letter ear (it was יי before, two yods); Tehillim perakim in the lab
page (type `t23`), lines = pesukim with Rabbi Alouf's times, "hear the hazzan" from the server when the mp3s are in
`static/tehillim/`, and the check sends the pointed line so the vowels are judged against the nikud too; the live
test (`t_live.py`) runs a pizmon line and a Tehillim pasuk through the real page and server (Tehillim 23:1, his own
audio as the take: 6/6 words ok, ע throat ✓, ח throat ✓, no vowel differences, no page errors).

**Not done, and why.** True fine-tuning of the whole encoder on the 5 hours does not fit 2 CPU cores (about 100
hours per epoch). The script for it is written and smoke-tested on CPU (`finetune_gpu.py`; free Colab T4, ~1.5 h,
`FINETUNE_GPU.md`); it is your call whether to run it. The site integration is a package, not a deploy (hard rule 1).

## 18. Honest standing after night 3
words **7/10** (unchanged: the calibration from your takes is still the missing piece), **ח 9/10**, **ע 8/10**
(a clean reader's ayin is now caught 99% by the head and 96% by the classifier with 3% false alarms on his alef;
the open question is still your voice, sung), vowels **5/10** (near-perfect on one clean voice, untested on
singing; shown as notes only). The scorecard script (`scorecard.py`) turns your pasted scorecard into the
thresholds that would have agreed with you.

# Night 4 (Oct 14, midnight – 6 AM): "get this better" — server v4.1

## 19. More data (tier 1: the rest of the archive; tier 2: public Egyptian Arabic)

**The rest of the archive.** The 3,000 lines of v3/v4 came from one recording per pizmon (the best one). The site
holds sync times for 1,121 recordings; `extract_lines2.py` took the other 700 (new voices first, lines with ע/ח
first, streaming the mp3s because the disk is nearly full): 1,900 more lines in 6 hours of CPU, 3,510 archive lines
after the quality filter (the older recordings fail it more often). The remaining ~5,500 lines are queued for
another night.

**Egyptian Arabic (FLEURS ar_eg, CC BY 4.0, 723 clips, 400 used).** The Arabic transcript mapped letter by letter onto
Hebrew letters (ع→ע, ح→ח, خ→כ, ه→ה, ق→ק, ص→צ …; the lam of al- dropped before sun letters, ta marbuta dropped,
words with ظ skipped), aligned on the Arabic ear like an archive line, src "eg". Many throats saying ع and ح, in the
model's home language. One in ten clips held out.

| letter head, held out | v4 (archive 2,153 + Alouf) | v5 (archive 3,510 + Alouf) | **v5eg (+ 370 Egyptian clips)** = shipped |
|---|---|---|---|
| hazzan ע→ע / א→א | 85% / 87% | 94% / 91% | **94% / 94%** |
| hazzan ח→ח / כ→כ | 93% / 96% | 97% / 94% | **98% / 90%** |
| Alouf ע / א / ח / כ | 99 / 99 / 100 / 100 | 100 / 99 / 100 / 100 | 99 / 100 / 100 / 100 |
| Israeli ע still heard as ע / ח as ח | 24% / 11% | 29% / 14% | **12% / 3%** |
| Egyptian ع→ע / ح→ח (never trained on, for v4/v5) | – | 86% / 100% | 93% / 100% |

The held-out hazzan set is larger now (373 lines of 41 pizmonim, their other recordings included) so v4's row is
not the same test, but a +9 on the hazzan ayin and a halving of the Israeli false "ayin" are beyond the noise. The
public data did what it was supposed to: the head learned the sound from more throats, not the language — v5
(never shown Arabic) already heard the Egyptian ع as ע 86% of the time. Throat classifier v4 (all 3,510 lines + Alouf +
Israeli): cross-validated AUC .96 (ע) / .98 (ח); held-out Alouf ע caught 95% with 3% false alarms on his alef; Israeli
ע called throat 12%, ח 5% — about the same as v3, kept.

Whole server, re-measured: Rabbi Alouf's 40 held-out pesukim ע **43 throat / 6 unsure / 0 plain**, ח 43 / 1 / 0, words
0 red of 318; 40 fresh Israeli sentences ע **1 / 25 / 22** (throat / unsure / plain), ח **0 / 12 / 65** (plain 84%, from
75%); 14 held-out hazzan lines (the others' recordings are not cached) ע 10 throat / 5 unsure / 0 plain.

## 20. The words check, measured the brief's way, and two new signals

**The studies.** (a) `eval_archive.py`: another hazzan's recording of a line, checked against the best recording
(right) and as another line of the same pizmon (every word wrong) — 16 pizmonim, 97 clips. (b) `words_study2.py`: the
same takes with one word's audio cut out (skipped) or two neighbours' audio exchanged (swapped); every other word is a
correct word that must not go red. (c) `words_study3.py`: the same tampering on CLEAN audio — Rabbi Alouf's held-out
pesukim, 40 of them — with and without a reference.

**What the archive takes showed.** On accompanied archive takes with the site's sync times, 12–17% of the UNTOUCHED
words already fall under the shipped red rule (skel < .2 and fit < .15); the hits sit at line starts (15 of 66 first
words), in two old recordings (28 Menaged 9/25, "mah nikhbad" 6/11) and in Sayegh's accompanied takes — the sync
starts late, the singer repeats or skips, the instruments cover him. So that test cannot set a red line below ~12%
false alarms; it only ranks rules. On clean audio the same rule flags 0.2% of right words. Your phone takes will sit
between the two; the scorecard decides.

**Letters kept (new).** The line's letters aligned on the letter head with EVERY letter optional at a cost of 3 nats
(`vowels.py letters_kept`): a letter is kept only where the head's evidence beats the cost of skipping it. Rabbi Alouf,
right words: 98% of letters kept, none of 318 words below half; the words of another pasuk: 33%; a skipped word:
20–50% (its neighbours' letters absorb some); its neighbours: 99%. The page now names the letters not heard in a
word that is red or yellow ("בים: ב not heard"). On accompanied archive takes the head hears little (28–35% of
intact words lose half their letters), so the signal is NOT a red rule on its own.

**The combined score pw (new).** Logistic on the reference-free signals (skel, letter head, vowel head, consonant
count, letters kept), fitted on the clean tampered pesukim; the hazzan fit is left out of it on purpose (fitted with
the hazzan being the same voice it over-trusts fit — it flagged ושמחה with skel .68 because fit was .26). Clean audio,
pw ≥ .9: **0.9% false alarms, skipped words caught 92–100%, swapped 50–59%, a wrong line 83%** (the shipped rule on
the same data: 54% / 11% / 22%). Archive takes: 59% false alarms — the heads cannot hear those takes, so the page
trusts pw only on a clean line (median letter-head score ≥ .7; Rabbi Alouf's lines .93, archive takes .31 — 100% vs
8% pass) and only at pw ≥ .95 for red; pw ≥ .8 makes a word "not sure" anywhere. Everything (kept, pw, the clean
flag, the vowel notes) is saved in the scorecard, so your verdicts can set the real thresholds (`scorecard.py`).

**Also:** one sentence per word that needs work (letters not heard, throat verdict, vowels, all in one line per
word); the Arabic ear's throat vote by its ع/ح peak; the reference cache keyed by server version (a stale cached
hazzan analysis had kept the old vote); a Space without the Tehillim audio says so and checks against the nikud only.

## 21. Honest standing after night 4
words **7.5/10** on clean takes (a skipped word is now caught 9 times in 10, a swapped pair 1 in 2, with under 1%
false alarms — on Rabbi Alouf's voice; on accompanied archive singing the new signals are switched off and the old
rule stands), **ע 8.5/10** (hazzan ayin 94% by the head, Israeli ayin rejected 88%, the whole-server vote never
"plain" on a clean reader), **ח 9/10**, vowels **5/10** (unchanged: proven on one reader), stability ✓. What I still
cannot measure without you: your voice on your phone — the scorecard.

## 22. The Space is live (Oct 15, night) — and v4.2

`https://davidsitt-pizmonim-dikduk.hf.space` (Docker, CPU basic; `/try` for someone else; `/health`). What it took:
- A new Hugging Face account has **no** free-CPU quota (`Quota exceeded for flavor cpu-basic … limit=0`, "Paused");
  PRO (~$9/month) unlocked it at once.
- Safari's web uploader fails ("Error: Load failed") on every file the Hub routes through LFS, which it decides by
  type (`*.pt`, `*.zip` … regardless of size: a 5 MB fp16 head failed like the 10 MB one). So the Space holds only
  Dockerfile + README and the Dockerfile pulls everything else from GitHub `davidsitt810-ops/dikduk-space` at build
  (an `ADD` of the branch's commit feed busts the cache when GitHub changes). Update = push to GitHub, then on the
  Space either a trivial README commit (rebuild with cached layers, ~2 min) or Settings → Factory reboot (~15 min).
- Measured on the Space (2 vCPU): a 16 s take against a cached hazzan line 17–18 s; Tehillim 23:1 (6 s) 13 s; a
  cold pizmon line adds ~12 s (download + analysis). The very first page check after start (warm-up running, cold
  line, 14 s ref + 16 s take) died at the proxy ("upstream request timeout" came back as the body). Same verdicts
  as locally on 200 line 3 (Shrem) and Tehillim 23:1.
- v4.2 therefore: `/check?…&job=1` queues the check (one worker thread) and the page polls `/job/<id>`, showing the
  stage ("listening to your take", "listening to the hazzan's line", seconds, queue position); the page prefetches
  `/ref` the moment a line is picked (analysed while the person records); the plain `/check` now runs in a thread
  so `/health` keeps answering; `torch.set_num_threads` = the cgroup CPU quota (os.cpu_count() reports the host's
  cores inside a container), reported in `/health` as `threads` / `cpu_count`. fp16 copies of the heads
  (`space_small/`, 5.2 MB each) give identical verdicts (46 words, 11 throat letters, 101 vowel slots: 0 changes)
  — not shipped, kept in case a size limit ever matters.
- Done Oct 23: the other 136 perakim are in `static/tehillim/` (144 in all, 102 MB, three commits); the Space gets them at the next Factory rebuild.

## 23. Shabbat round (Oct 23): whole-line evidence, the exam on Rabbi Alouf, two vote fixes — v4.3

**The exam** (`space_test/exam_alouf.py` → `exam_rules.py`): 70 pesukim from the 14 perakim the heads never saw
(7, 12, 18, 21, 23, 32, 35, 40, 46, 94, 118, 123, 126, 140), each run five ways — intact; one word's audio cut out;
two neighbours' audio swapped; one word's audio replaced by another word's from the same perek; the whole pasuk
checked as another pasuk. 2,666 word verdicts. Reference = his own intact pasuk, as on the Space.

**New signals** (`space/order.py`, on the letter head's log-probs, ~0.3 s per line): `drop[j]` = best-path score of
the line without word j minus the line as written (nats); `swap[j]` = the same for words j, j+1 swapped; `gap` =
(free path − written line) per frame. Phone-recognizer versions too (`_ph`), weaker, not used yet.

| rule on clean takes | right words red | right words "not sure" | skipped caught | swapped caught | replaced caught | wrong line |
|---|---|---|---|---|---|---|
| shipped (v4.2) | 0 / 1,850 | 2–4% | 96% | 45% (18% passed) | 76% | 17% words, no line verdict |
| v4.3 | **0 / 1,850** | **0.4%** intact, 1–2% in tampered lines | **97%** | **92%** (2% passed) | **79%** | **100%** at line level |

v4.3 rule (page, embed and server identical): markOf as before, plus on a clean take — the line's **largest drop** ≥ 10
and ≥ 4 above the second → that word "not heard"; the line's **largest swap** ≥ 8 → both words "seem swapped";
**gap ≥ 0.6** → "this does not sound like this line" (intact lines max 0.11, one skipped word p50 0.18, wrong lines
p05 0.69); a **rescue**: kept ≥ .75 and head ≥ .6 and pw < .8 → the word is there whatever its consonant score (0 wrong
words rescued of 445); and **without a hazzan** a low consonant score is red only when the head also missed letters
(Tehillim without audio: 0 false alarms instead of 3). Winner-take-all is what keeps false alarms at zero: a
skipped word's neighbours also gain from being dropped, just less.

**Throat votes.** ח now votes with the v2 classifier (v1 kept 8 of 79 of his ח "unsure" against the head and the
Arabic ear): Alouf ח 79/79 from the throat; fresh Israeli ח said like כ: 92% plain, 8% unsure, 0% throat (was 84/16/0).
ע: when neither the Arabic ear nor the head heard any throat sound (ع peak < .1, head ע mass < .05), that counts as
plain like a heard alef does: Israeli ע 65% plain / 33% unsure / 2% throat (was 46/52/2); Alouf ע unchanged 63 throat /
11 unsure / 1 plain of 75 (the plain one: בערים 94:8, mid-word, v2 .09, Arabic alef). By position on Alouf: ע start
79% throat / 21% unsure, mid 95%, end 43% / 57% unsure — his word-final ע is soft (register §: 47% pharyngeal).
A plain ע/ח is now a fault only where the hazzan's own letter in that word was judged from the throat.

**Vowels** vs nikud on the 70 intact pesukim: 6 notes over 1,191 slots (0.5%). **Speed**: 3.0 s per 6 s pasuk in
process on 2 CPUs (with the new signals).

**Still open**: replaced words that resemble the original (באדני for אדני, ברד for עברו) pass or stay "not sure";
ע at word start on Alouf 21% "unsure" (v2 conservative where Israeli word-initial ע is zero); nothing of this is
measured on a student's voice yet — the booth exists for that. The Space runs v4.3 after one Factory reboot; the
page and the embed already carry the rule and work against the old server (the new fields are simply absent there).

## 24. Shabbat round, second half (Oct 23 night – Oct 24): the pizmonim exam and v4.4

**The gap in the testing.** Everything measured so far was Rabbi Alouf reading, checked against himself: clean
a-cappella, same voice. The site's use is a student singing a *pizmon* against *another* hazzan's recording. The
archive has that case ready-made: 15 pizmonim with two or more synced recordings in the cache. `exam_archive.py` takes
hazzan A's line as the reference (as the site does) and hazzan B's line k as a RIGHT take (another voice, often with
instruments), the same clip as line j of the same pizmon as a WRONG LINE, and, where B's take is clean, a word cut out
(SKIP) and two neighbours swapped (SWAP) from the machine's own placement. 216 takes, 1,172 word rows
(`exam_archive_rows.json`). The ground truth is only as good as the site's sync events: 11 "right" clips are shorter
than half the hazzan's line or twice as long and are left out of the tallies; a few lines are plainly sung with
other words than the site's text (the same words red in two independent recordings: ביום in 31:3, בחכמה כלם in 34:3,
לעם בחר in 17:3). 79 of 205 takes are on recordings the letter head was trained on; the rest are new to it.

**What it showed (v4.3 as shipped that morning).** On the 87 plausible right takes, **a right word went red 8.6% of
the time** and "not sure" 45%. Only 9 of 87 takes were CLEAN (median letter-head score ≥ .7), and on a non-clean take
the per-word rule was still the v3 rule: red when the phone recognizer finds neither the word's consonants (skel < .2)
nor the hazzan's sounds (fit < .15) — two readings of the one ear that hears least in sung, accompanied audio — and
the letter head was never asked. The whole-line evidence and the line gap were switched off on every non-clean take,
which also meant **a wrong line never produced the "not this line" headline** (a wrong line is non-clean by nature:
on Alouf the gap caught 70/70 as a number but 0/70 as a verdict — a bug since v4.3's rule went in).

**v4.4** (server `marks_of`, page and embed identical; `t_parity.py` runs the two JS copies in node on every exam row
against the server's python: 541/541 lines agree):
1. **Non-clean take, red needs the head to agree**: the skel/fit red is "not sure" when the head heard half or more of
   the word's letters (kept ≥ .5).
2. **The pw-red yields to a found hazzan fit**: on a clean take pw ≥ .95 is red only when the hazzan's own sounds for
   the word were not found (fit < .5) — אשר in 29:3 had fit .92 and went red on pw alone.
3. **CLEAN is robust**: the median letter-head score with the lowest word left out (three or more scoreable words).
   One wrong word in a short line was pushing the median under .7 and switching the whole-line evidence off exactly
   when it was needed: Alouf swaps caught 92 → 99%, skipped 97 → 99%, no new false alarm.
4. **The line gap speaks on every take.** Measured safe: 0 of 157 right takes (70 Alouf + 87 archive) reach .6; the
   archive's right takes top out at .45. It catches all 70 Alouf wrong lines as a verdict now, and 4 of 76 archive
   wrong lines (in noisy audio the free path is not much better than the forced wrong line — the gap is honest there).
5. **"I could not make out the words"**: a non-clean take whose robust head median is under .3 (and whose gap does not
   say "wrong line") gets that headline, nothing red, the doubtful words "not sure". Alouf never triggers it (his
   lowest intact median is .80); 16 of 87 archive right takes do — the heavily accompanied ones, where the reds were.

| | right words red, Alouf (1,850) | skipped | swapped | replaced | wrong line (verdict) | right words red, archive (456) | archive takes "cannot hear" |
|---|---|---|---|---|---|---|---|
| v4.3 | 0 | 97% | 92% | 79% | 0/70 (!) | **8.6%** | – |
| v4.4 | **0** | **97%** | **96%** | 77% | **70/70** | **0.9%** | 29 of 87 |

What is left red on the archive's right takes (16 words) is, by every ear at once, not in the clip: words the singer
does not sing as written, or cut off by the sync. Two borderline ones remain (hskel .3–.5 with kept .5–.67).

**Later the same night, three more.** (6) **No singing at all** (silence, noise, a microphone that missed the
person): the phone recognizer hears ~4 phones a second in reading, 1.5 in slow singing, 0 in noise — under 3 phones
or one per two seconds the headline is "I did not hear any singing", nothing is judged (pure noise used to come out
as "This does not sound like this line" with every word red). On a take the head could not make out, the ע/ח and
vowel claims are dropped too. (7) **A skipped word was being called "swapped" with its neighbour** (the archive's skip
takes: לישראל cut → "לישראל and אורה seem swapped", the neighbour red): a missing word also gains a little from a
swap (8–14 nats against a drop of 27–72). Now when the line's dropped word sits in the best swap pair, the swap must
gain at least 0.35 of the drop (real swaps 0.8–3.3 on Alouf, 52 of 52; skips 0.12 and 0.31) — archive skip false
alarms 4 → 0, Alouf swaps still 134/136. (8) **Swaps on a half-heard take** (head median .5–.7): the swap evidence is
safe there at a higher bar (right archive takes top out at 5.8 nats, real swaps 12–62): swap ≥ 12 → archive swaps
caught 40 → 75%, Alouf 136/136; the drop evidence stays clean-only (right words reach 40+ nats on such takes).

**An independent review** (a second agent that had not seen the work, with a 240,000-line synthetic fuzz of the
three copies) found: the skip-vs-swap guard only worked when a single word had won the drop (two skipped words in
one line, or a skipped one-consonant word, could still flag a sung neighbour as "swapped") — the guard now uses the
pair's own largest drop; the scoreboard collapsed repeated words (קדוש קדוש קדוש) into one — it now scores by
position; an empty fit list counted as a hazzan on the page ("as the hazzan sings it" with nothing compared) — now
it is "no hazzan" in all three copies; `head_median` took the upper middle, so one well-heard word made a 2- or
3-word line "clean" — now the lower middle (the true median). The last one costs a little on Rabbi Alouf (swaps
caught 99 → 96%, skipped 99 → 97%, replaced 80 → 77%: short pesukim whose two swapped words are the two poorly heard
ones are "not sure" instead of red) and buys a lot on the pizmonim archive: right words red 3.5% → **0.9%** (4 of 456,
all of them words the singers do not sing as written), with 29 of 87 accompanied takes now "I could not make out the
words". Also from the review: `/score` survives one broken record, `score_take` tolerates older summaries, a word
with no verdict gets no "letters not heard" note.

**Validation on pesukim the thresholds never saw** (`exam_alouf.py 80 11` with the first batch's pesukim excluded:
80 fresh held-out pesukim, 3,255 word rows, `exam2_rows.json`): right words red **0 of 2,290**, intact "not sure"
0%; skipped word caught **78/80**, swapped **155/156**, replaced 56/80 (70%; the weak case, as known), wrong pasuk
**78/79** as a verdict (the 79th: gap 0.59). Throat on the 80 intact pesukim: ע 90% throat / 10% unsure / 0 plain
(start 40/4, mid 57/2, end 5/5), ח 70/71 throat; vowel notes against the nikud 12 of 1,426 slots (0.8%).

**Other things done this round.** All 144 perakim of Rabbi Alouf's Tehillim are in the repo (`static/tehillim/`,
16 kHz mono 48 kbps, 102 MB, three commits; the Space gets them at its next Factory rebuild) — until then the page
decides per perek from the server's own list whether a hazzan exists (it used to assume audio for every perek once
any was present: broken play buttons and a failed hazzan request on perek 94, say). Swaps involving a short word
(על/פניהם, עמו/ואשתמר) are caught (one side n ≥ 2, the other n ≥ 1; 6/6 on the tampered test takes); one swap pair
per line (the largest); no vowel or throat notes on a word that was not there; the booth's scoreboard matches words
by their letters (final forms), says when the machine could not hear a take, and when it called the line wrong.
The exam of the morning (`exam_alouf.py`) and the pizmonim exam, the two-gate report (`exam_report.py`, which takes
the rule out of app.py itself), the variants (`exam_variants2.py`), the truth filter (`exam_archive_truth.py`) and
the parity test are in the repo's `tools/`.

**Still open.** (a) Nothing is measured on a student's voice yet — the booth and David's 20 recordings are the
calibration that matters most. (b) The archive exam's ground truth is the site's sync events; a cleaner archive
test needs lines whose second recording is known to carry the same words. (c) Replaced words resembling the original
still pass or stay "not sure" (באדני for אדני). (d) ע at word start on Alouf 21% "unsure". (e) One-consonant words
are never red on their own (רעה, את, עמו skipped → "not sure"): the Alouf rows show the drop evidence cannot
separate them safely (right one-consonant words reach drop 8.3, a skipped עמו 9.9).

## 25. Other voices (Oct 24, small hours): the wrong-line verdict rebuilt on the text's own lines — v4.5

**The test.** Everything so far was Rabbi Alouf against himself, or the archive's hazzanim. A student is neither.
`exam_israeli_words.py` runs 80 FLEURS he_il sentences — Israelis reading modern Hebrew, held out of all training,
clean recordings, no hazzan — against their own transcripts (RIGHT), with a word cut (SKIP), two swapped (SWAP) and
as another sentence (WRONG LINE). It is a stress test, not the student case (fast modern speech, 16-word sentences,
foreign names and numbers the transcripts write in Latin letters), but it is the only "other voices" data at hand.

**What it showed.** The letter head reads these voices poorly: head median p50 0.53 (Alouf ≥ 0.80), 2 of 80 takes
"clean", right words "not sure" 53%. The honest failure mode — but one verdict was not honest: **the free-path gap
called 33 of the 80 right sentences "This does not sound like this line"** (gap ≥ 0.6; Israeli right takes have gap
p50 0.50, p95 1.63, against Alouf's max 0.11). A voice the head reads poorly raises the gap exactly like a wrong
text. Right words red 2.4% — of which about four fifths are FLEURS's own faults (two clips whose audio stops before
the transcript ends; English words and numbers in the transcript that `he_words` drops), the rest a handful of
words at 0 on every ear and one false "swapped" pair (ביתר פירוט, head median .52, swap gain 35.7 — the one
half-band false alarm in 46 Israeli + 31 archive right takes).

**v4.5 — the rival line.** `order.rival_evidence`: the server scores the text's *other* lines (the perek's other
pesukim, the pizmon's other lines; `/check?pid=…`, or `alts=a|b|c`) on the same head matrix and reports how much the
best of them beats the written line, per frame. A wrong pick shows as a large positive gain whoever sings; a poorly
read voice does not (both lines suffer alike). Rule (server, page, embed; parity 541 + 397 lines): **wrong line =
another line beats the written one by ≥ 0.3 nats/frame AND that line itself fits the audio (its own gap to the
free path ≤ 0.4)**. The free-path gap alone no longer decides anything (shown in the lab line only). Calibration
(`calib_rival.py`, `calib_rival.json`): Alouf right pasuk vs the perek's others: gain max −0.26 (the written pasuk
always wins); Alouf wrong pasuk: min +0.40, the true pasuk's own gap ≤ 0.09 → **70/70 caught, 0/70 false**. Israeli
right sentence vs five others: 0/80 called wrong (the six with gain ≥ 0.4 all had the rival fitting badly too, gap −
gain ≥ 0.49: an unreadable voice, not a wrong text); Israeli wrong sentence: 26/80 caught — the rest are voices the
head cannot read, and those now get "I could not make out the words of this line — check that it is the right line"
instead of a confident wrong verdict either way. Without the text's other lines (free typed words) there is no
wrong-line verdict at all.

**Also this round:** a "plain" ע/ח on a take the heads hear poorly is not shown as a fault (the archive's other
hazzanim: 9 plain verdicts, all on such takes; Israelis: ח 156 plain of 174 — real, they say כ — and ע 87 plain / 39
unsure / 4 throat of 130), and the vowel ear is consulted only on a clean take (117 notes on 528 right archive words
otherwise, 0.5–0.8% on Alouf). The booth's scoreboard says per take whether it was clean.

**Re-measured end to end with the text's other lines passed to every check** (`exam_r1.log`, `exam_israeli2.log`,
`exam_archive3.log`; rows in the repo's `tools/`):

| v4.5 | right words red | "not sure" | skipped caught | swapped caught | replaced | wrong line called | right take called wrong | "cannot hear" |
|---|---|---|---|---|---|---|---|---|
| Rabbi Alouf, 70 pesukim | 0 / 1,850 | 0–2% | 67/69 | 130/136 | 54/70 | **70/70** | 0/70 | 0 |
| Rabbi Alouf, 80 fresh pesukim | 0 / 2,290 | 0–1% | 78/80 | 155/156 | 56/80 | 78/79 | 0/80 | 0 |
| archive, another hazzan + instruments, 87 takes | 4 / 456 (0.9%) | 53% | 7/10 | 14/20 | – | 12/72 (+48 "cannot hear") | 0/87 | 29/87 |
| 80 Israelis reading, no hazzan | 8 / 1,271 (0.6%) | 32% | 27/80 | 59/158 | – | 23/78 (+48 "cannot hear") | **0/80** (was 33) | 10/80 |

The server/page/embed parity holds on all of it (`t_parity.py`: 938 recorded lines + synthetic rivals). Also: the
text's other lines are looked up in the worker, not on the event loop (the site's lyrics may be fetched there).

## 26. The letter head retrained on other voices (Oct 24, small hours) — head v7

**Why.** §25's test showed the letter head reads voices it was not trained on poorly (Israelis: head median .53,
2 of 80 takes clean, half the words "not sure"). The head had never trained on a non-hazzan voice: the 119 Israeli
dev clips in the manifest were an exam set only.

**Data.** FLEURS he_il *train* split (CC BY 4.0, 1.8 GB tar, streamed): 1,500 clips of Israelis reading, 2–20 s,
transcripts without digits or Latin letters, **ע written as א and ח as כ** in the targets (that is how they say
them, so the head learns their voices without learning that an alef sound is an ayin); features = the Arabic
model's layer 12, as for everything else (`extract_il_train.py`, src `il2`). Trained warm from the shipped head,
3 epochs, LR 3e-4, Alouf ×2, archive ×1 (`train_head2.py letters 3 … HEAD_IL=1`).

| head | held-out hazzan lines LER / ע→ע | held-out Alouf LER / ע→ע | Israeli dev LER / ע→א | Egyptian ع→ע (throat speakers unseen) |
|---|---|---|---|---|
| v5 (shipped) | 25% / 94% | 7% / 100% | 63% / 71% | 86% |
| v6 (+Israeli) | 26% / 93% | 7% / 99% | **31%** / 98% | **19%** |
| **v7 (+Israeli +Egyptian)** | 26% / 92% | 6% / 98% | **32%** / 96% | **78%** |

v6 learned "an unknown voice's throat sound is an alef" (the Egyptian column): a student's real ע would have lost
the head's vote. v7 adds the 410 Egyptian Arabic clips (ع ح from the throat, mapped to Hebrew letters) and keeps
both. On the full exams, v7 against v5, same rule:

| | Alouf 80 fresh pesukim: FA / skip / swap / replaced / wrong pasuk | Israeli 80: clean takes / head median / "not sure" / red / skip / swap / wrong line | archive 87 right takes: red / "not sure" / clean |
|---|---|---|---|
| v5 | 0 / 98% / 99% / 70% / 79/79 | 2 / .53 / 32% / 0.6% / 34% / 37% / 23/78 | 0.9% / 53% / 9 |
| v7 | 0 / 98% / 99% / 71% / 79/79 | **15** / **.65** / **21%** / 1.3%* / **46%** / **75%** / **60/78** | (below) |

\* 16 words, 12 of them in sentences whose transcript has digits, Latin letters or quotes that `he_words` drops (the
audio says them, the written words do not): on clean-transcript sentences 4 of ~1,000 — the same ביתר/פירוט pair as
before, and one dropped word. Alouf's throat verdicts are unchanged with v7 (ע 90% throat / 10% unsure, ח 99%).
Also from the Israeli run: a "dropped" word whose consonants the phone recognizer found in place (skel ≥ .8, kept ≥ .6)
is now doubtful rather than red (1 of 202 true catches on Alouf had that).

**Archive with v7** (87 plausible right takes): right words red 9 of 456 (2.0%; v5: 4), clean 14 (v5: 9), one right take
called the wrong line — pizmon 17 line 1 in 'mah nikhbad.mp3', where the rival line (הנחילו יה צור עולמים) has a head
median of .80 against .24 for the written line: the clip holds line 2, the site's sync is off, the machine was right.
Wrong lines called 11 of 98 (the rest unreadable with instruments). The wrong-line verdict now also requires the
rival line to be heard itself (its own head median ≥ .3, `rival.head`): no cost on Alouf (70/70) or the Israelis
(65/80 caught with v7, 0/80 false).

**Shipped as v4.6**: head v7 is `letter_head.pt` (v5 kept as `space_test/letter_head_v5_shipped.pt`); the rule is
v4.5's plus the drop guard and the rival-head condition; parity 547/547; the regression suite green.

**The shipped v4.6 on all 199 held-out Israeli clips** (the 80 fresh + the 119 that served the head's own exam; none
trained on; `exam_israeli_all_*.json`): right takes clean 36/199, head median p50 .64, "not sure" 22%, red 1.6% —
but split by the transcript: on the 123 sentences whose transcript has no digits, Latin letters or quotes (which
`he_words` drops while the audio says them), **right words red 0.4% (8 of 1,803), "not sure" 16%**; on the other 76,
red 3.0% (the written words are not what was said). No right sentence called the wrong line (0/199); the wrong
sentence called 153/199; a cut word caught 46%, swapped words 70%. ע on Israelis: plain 262 / unsure 78 / throat 5 of
345 (they say it plain: "throat" 1.4% is the false-confirmation rate), ח plain 353 of 374.

**Not done, on purpose:** refitting the word logistic (`WORD_MODEL`, pw) on the v7 head's features. It would cut the
Israelis' "not sure" from 16% to 6% (archive 53 → 42%) but halves the replaced-word catch on Rabbi Alouf (57 → 33 of
80): pw ≥ .95 is what catches a replaced word on a clean take. A knob for later, with a learner's voice in hand.

## 27. The letter checker (Oct 24, evening–night) — v4.7

David's ask: "a letter checker where I say just the letter and you tell me right or wrong, and show it properly."
Built as `/letters` + `POST /letter` (`space/letters.py` holds the logic; `app.letter_probe` runs the ears).

**Design.** A letter cannot be said alone, so the student says it with a vowel (עַ), by its name (עַיִן), or in a
word Rabbi Alouf says that opens with it (עַמֶּךָ) — all three open with the letter, so the checker judges the take's
OPENING consonant and nothing after it: trim the silence (20 ms RMS, the louder of −35 dB and 5% of the peak), find
the onset with both ears (each ear's first confident symbol at or after the energy onset; the earlier one), close the
window a little after each ear's second symbol (the vowel, or the next consonant when the vowel was not heard;
whichever comes first), and read every ear's peaks in that window: the phone ear's symbols, the Arabic ear's letters,
the letter head's letters, the throat classifiers. The "hear him" examples are his own word-initial letters cut from
the Tehillim (`tools/make_letters.py`: 94 mp3s, 490 KB), chosen among the ones the checker itself hears right.

**The study** (`tools/letters_study.py`, 4,843 cuts, `letters_rows.json`): word-initial letters cut as a student would
record them — Rabbi Alouf's (120 per letter and variant; the nikud gives dagesh / rafe and shin / sin) and Israelis
reading (FLEURS dev + fresh, 199 sentences, the machine's own word placement), whose ע ח ק ט צ ר are the Israeli
sounds. Verdict per letter, Rabbi Alouf called right / wrong / not sure — Israelis caught / called right:

| letter | rule | Alouf | Israelis |
|---|---|---|---|
| ע | head ratio ≥ .6 / ≤ .3 (mass ≥ .2; neither heard = a plain vote), v2 classifier ≥ .5 / ≤ .3, Arabic ع ≥ .4; two votes and none against | 70% / 5% / 25% (clean onsets 80% / 2%) | 74% / 0% |
| ח | the same with ح, classifier ≥ .6, a khaf heard (خ / ه / phone x ≥ .5, ح < .15) a plain vote; no "neither heard" vote | 81% / 1% / 18% | 76% / 4% |
| א | the ע ears read the other way | 82% / 0% / 18% | (right 93%) |
| ק | Arabic ق ≥ .5 and > ك: right; ك ≥ .5 and ق < .2: wrong | 84% / 1% (a/o/u words) | 89% / 2% |
| ט | ط vs ت | 84% / 6% | 64% / 0% |
| צ | ص vs س (and the phone ear's ts) | 88% / 4% | 63% / 5% |
| ר | rolled: ر ≥ .5 or phone r ≥ .4, and غ < .3; from the back: غ ≥ .3 and ر < .15 | 82% / 2% / 17% | 30% / 18% (some do roll it) |
| בּ b / ב v | phone b vs v (the Arabic ear has no v) | 86% / 2%; v on his vav-initial words 66% / 8% | – |
| כּ k / כ kh | k, ك vs x, χ, خ | 96% / 0; 87% / 3% | – |
| פּ p / פ f | p, ب vs f, ف | 90% / 0; 88% / 0 | – |
| שׁ / שׂ | ʃ, ش vs s, س | 99% / 0; 94% / 1% | – |
| ת | t, ت vs s, θ, س, ث | 84% / 1% | (right 84%) |

**What the study taught.**
1. *At the start of a word the Arabic ear's alef is not evidence of a plain ʿayin*: it writes an alef (the hamza seat
   Arabic spelling wants there) for 34 of Rabbi Alouf's 120 word-initial ע; the line checker's "alef heard → plain"
   vote would have left 38% of them "not sure". Dropped for the letter checker; the ع peak keeps its throat vote
   (62% of his, 7% of the Israelis').
2. *The emphasis lives in the vowel.* Rabbi Alouf's ק before a sheva is heard as ك 13 of 19 times, before i/e half
   the time, before a/o/u 1 of 80; his צ before i/e is س 15 of 38 times, before a 1 of 39. The checker asks for the
   letter with "a" and the examples are such words.
3. *Rabbi Alouf says a word-initial ב without dagesh as b* — 110 of 120 (קִי בָנוּ, יִשָּׂא בְרָכָה…), while his vav is v
   (88 of 120 first phones) and his word-initial כ without dagesh is kh (69 of 79): the ear is fine, the reading is
   what it is. The vet examples therefore come from inside words (לָרֹכֵב, אוֹיֵב, אָהַבְתָּ), and the page tells the
   student to say just the letter there.
4. *The Israeli r is mostly nothing to these ears*: heard as غ in 30%, as a rolled r in 18% (plausibly real: Israelis
   of Mizrahi or Russian background roll it), as nothing in half. So ר confirms a rolled r and says "I did not hear a
   rolled r" otherwise — not "wrong".
5. A cut artifact in the Israeli set: a word's cut often holds the tail of the previous word's consonant, so the
   "onset" lands on it; on cuts with a clean onset ע is 80% / 2% on Rabbi Alouf and 78% / 0% on Israelis. The
   energy-anchored onset (symbols more than 50 ms before the take's energy onset are ignored) came out of the
   end-to-end test on the example snippets, 14 of which had landed in the leading quiet.

**Strict mode** (`strict=1`, a checkbox on the page): "not sure" becomes "not clearly right — work on this one".
**End-to-end** (`tools/t_letters.py`): the 94 example snippets posted back → right or not sure, never wrong; Israeli
cuts for ע ח ק never right; silence and a tone → "I did not hear anything"; bad inputs → 400; the page drives through
a fake microphone in Chromium (`flow_letters.py`): record → post → ✓ with all three ears.
