# tools — how the checker is tested

These scripts run from the dikduk chat's workspace (they need Rabbi Alouf's mp3s, the alignment index and the local
server); they are here so the method is on record.

- `exam_alouf.py` — the exam: held-out pesukim intact and tampered four ways (skip, swap, replaced word, wrong line)
  through `app.analyse`; writes `exam_rows.json` / `exam_lines.json`.
- `exam_rules.py` — the word rule measured on those rows (false alarms, catches, thresholds), throat verdicts by
  position, vowel notes.
- `exam_throat.py` — throat verdicts on the intact pesukim through the live server; `exp_israeli_fresh.py` — the
  false-"throat" test on Israeli read speech (FLEURS he_il).
- `blind_test.py` — a folder of recordings + `manifest.txt` → the machine's claims per recording, as the page says them.
- `t_live.py`, `t_rule.py`, `t_booth.py`, `t_space_check.py`, `shot.py` — the page, the rule, the booth and the API
  driven in a headless phone browser against a server URL.
- `LAB_NOTES.md` — the whole history with numbers; `SPACE_SETUP.md` — how the Space is set up and updated;
  `SITE_HANDOFF.md` — what the site chat gets.
