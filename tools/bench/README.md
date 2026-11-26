# The test bench

What every measured change to the ears or the rules is tried on before it ships. Rebuilt on Nov 25 after the first
one was lost with its machine (it lived in a scratch folder); the scripts now live here and the costly results are
copied somewhere durable after every exam (`save.sh`).

## What it needs

- A folder for the bench (`$B`) with `venv/` — Python 3.11 with `torch==2.4.1+cpu`, `transformers==4.44.2`, `numpy`,
  `fastapi`, `uvicorn`, `python-multipart` (torch 2.4.1 has no wheel for Python 3.13) — and room for `hf/` (the
  models, about 2.5 GB, fetched on the first start).
- Any Python 3 with `requests`, `numpy` and `playwright` for the exams and the page tests; `ffmpeg`.
- Readers the heads never heard. The recordings stay out of the repo:
  - Hazzan Faraj Samra's Tehillim, one mp3 per perek (`SephardicHazzanut/1.Tanach/3.Ketubim/Tehillim/PerekNNN.mp3`
    on David's Mac, 128 perakim) as `$LAB/data_samra/NNN.mp3`;
  - LearnTefillah's haftarot (one reader; `SephardicHazzanut/learntefillah/files/17-Haftara/` on the Mac), with the
    list of his pesukim the Mac batch lined up (`dikduk_lab/out/bench_lthaf_items.json`, made there from
    `man_lt_lthaf.jsonl` and `lt/texts/`).

## The steps

    bash tools/bench/server.sh $B                      # the dev server of this checkout on 127.0.0.1:7861
    PORT=7862 bash tools/bench/server.sh $B            # a second one beside it (page tests while an exam runs)
    python3 tools/bench/bench_index.py $LAB            # Rabbi Alouf's lines and times, as the page uses them
    cp nikud.py $LAB/tehillim/                         # + ctcutil.py (kept with the lab code, not in the repo)
    PY=$B/venv/bin/python HF_HOME=$B/hf bash tools/bench/align.sh $LAB samra "$LAB/data_samra/%03d.mp3"   # 99 minutes
    bash tools/bench/chain.sh $LAB samra 110 <durable folder> samra_rec_B:56-150:-:450 samra_phone_B:56-150:phone:450 samra_noisy_B:56-150:noisy:450
    python3 tools/bench/lt_jobs.py bench_lthaf_items.json <where the recordings are> $LAB/lt/jobs_lthaf.json 300 20
    DK_LAB_V=$LAB/v python3 tools/bench/exam_items.py $LAB/lt/jobs_lthaf.json lthaf_rec      # DEGRADE=phone for the phone
    export DK_LAB_V=$LAB/v
    python3 tools/bench/replay.py samra_phone_B lthaf_rec     # what the page shows: the correct reading, five planted kinds
    TRUST=off python3 tools/bench/replay.py samra_phone_B     # the same takes with the take's gate alone (v5.9)
    RULESETS='vp=.3,vpu=.6;vp=.5,vpu=.6' python3 tools/bench/replay.py samra_phone_B        # other bars
    python3 tools/bench/replay.py --live <an exam from a server that rates its notes>        # its numbers = the replay's?
    python3 tools/bench/notes_table.py samra_rec_A samra_phone_A samra_noisy_A               # every note with its facts
    CV=1 python3 tools/bench/trust.py samra_rec_A+samra_phone_A+samra_noisy_A                # what each group of facts adds
    FEATS="bias,hskel,vskel,m,you,you*c,ref,ref*c,none,you far,ref far" OUT=w.json python3 tools/bench/trust.py samra_rec_A+samra_phone_A+samra_noisy_A
    TRUST=w.json python3 tools/bench/replay.py samra_phone_B  # weights tried before they are written into vowels.py

An exam keeps the server's whole answer for every take (`exam_<name>.full.jsonl`, about 20 KB a take, 4 KB gzipped).
The take's vowel slots do not depend on the nikud, so one run of the correct reading serves all five planted
mistakes (`tools/plant.py`) and any new rule: `replay.py` rewrites the answer as the server would have given it for
the planted line and passes it to `rule.summarize` itself. `replay.py --check` compares that with a real planted run
of the server (the same on every take of the runs tried: 10 takes as recorded, 10 with noise, 40 on a phone, each
for two planted kinds).

Other tools: `check_take.py 23 2 take.m4a --words` (one recording as the lab page checks Tehillim, every note with
its second opinion and trust), `wordgate.py` (the phone ear's opinions on false notes and on catches; simple rules on
the note tables), `ear2.py` (the phone ear as a vowel checker of its own: tried, not built), `name_check.py` (the Name
read "Elohim", before and after).

## The page tests

    bash tools/bench/demo_site.sh $B/demo              # a site page with this checkout's embed.js, on 127.0.0.1:8099
    python3 tools/t_vlost_ui.py                        # and t_noisy_ui.py, t_learn_ui.py, t_shva_ui.py, t_rule.py ...
    bash tools/bench/demo_site.sh $B/demo2 http://127.0.0.1:7862 8098     # the same against the second server:
    DK_URL=http://127.0.0.1:7862 DK_DEMO=http://127.0.0.1:8098 python3 tools/t_vlost_ui.py

## Speed (two cores)

A take of 8 seconds: about 4 seconds as recorded with the hazzan's line already heard once (the server keeps it), 7
the first time, twice that while a second job runs. 450 takes: half an hour to an hour. A haftarah pasuk (12 seconds):
10 seconds beside another exam.

## Do not

Edit `exam.sh`, `chain.sh` or `exam_voice.py` while a chain is running: bash reads a script as it goes (a run on
Nov 25 lost its log that way), and each exam starts a fresh Python that imports this checkout's `rule.py`.
