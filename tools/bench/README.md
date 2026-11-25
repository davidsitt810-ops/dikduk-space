# The test bench

What every measured change to the ears or the rules is tried on before it ships. Rebuilt on Nov 25 after the first
one was lost with its machine; this time the scripts live here and the costly results are copied somewhere durable
(`save.sh`).

## What it needs

- A folder for the bench (`$B`) with `venv/` — Python 3.11 with `torch==2.4.1+cpu`, `transformers==4.44.2`, `numpy`,
  `fastapi`, `uvicorn`, `python-multipart` (torch 2.4.1 has no wheel for Python 3.13) — and room for `hf/` (the models,
  about 2.5 GB, fetched on the first start).
- Any Python 3 with `requests`, `numpy` and `playwright` for the exams and the page tests; `ffmpeg`.
- A reader's Tehillim the heads never heard, one mp3 per perek: Hazzan Faraj Samra's
  (`SephardicHazzanut/1.Tanach/3.Ketubim/Tehillim/PerekNNN.mp3` on David's Mac, 128 perakim) as `$LAB/data_samra/NNN.mp3`.
  The recordings stay out of the repo.

## The steps

    bash tools/bench/server.sh $B                      # the dev server of this checkout on 127.0.0.1:7861
    python3 tools/bench/bench_index.py $LAB            # Rabbi Alouf's lines and times, as the page uses them
    cp nikud.py $LAB/tehillim/                         # + ctcutil.py (kept with the lab code, not in the repo)
    PY=$B/venv/bin/python HF_HOME=$B/hf bash tools/bench/align.sh $LAB samra "$LAB/data_samra/%03d.mp3"   # ~1 hour
    bash tools/bench/exam.sh $LAB samra samra_phone 56-150 phone       # one run per kind of recording: - / phone / noisy
    DK_LAB_V=$LAB/v python3 tools/bench/replay.py samra_phone          # the page's verdicts, the five planted kinds
    DK_LAB_V=$LAB/v python3 tools/bench/notes_table.py samra_phone     # every note with what is known about it
    bash tools/bench/save.sh $LAB <somewhere durable>

An exam keeps the server's whole answer for every take (`exam_<name>.full.jsonl`, about 20 KB a take). The take's
vowel slots do not depend on the nikud, so one run of the correct reading serves all five planted mistakes
(`tools/plant.py`) and any new rule: `replay.py` rewrites the answer as the server would have given it for the planted
line and passes it to `rule.summarize` itself. `replay.py --check` compares that with a real planted run (10 of 10
takes the same, for EI and OU, as recorded and with noise).

One recording by hand, as the lab page checks Tehillim: `python3 tools/bench/check_take.py 23 2 take.m4a --words`.

## The page tests

    bash tools/bench/demo_site.sh $B/demo              # a site page with this checkout's embed.js, on 127.0.0.1:8099
    python3 tools/t_vlost_ui.py                        # and t_noisy_ui.py, t_learn_ui.py, t_shva_ui.py ...

## Speed

Two cores: a take of 8 seconds takes about 6 seconds with the hazzan's line already heard once (the server keeps
it), twice that while something else runs. 450 takes: about an hour.
