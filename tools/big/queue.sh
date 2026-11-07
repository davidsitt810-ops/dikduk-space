#!/bin/bash
# Bigger tests over Shabbat: each call runs ONE step, the first not yet done, and every step ends well inside the
# 2-hour limit for one background job; call it again for the next. Exit 0 with "all done" when nothing is left.
# Order: Faraj i->e planted comes before his Tehillim 56-150, so a rule can be tuned on 1-55 and then checked on 56-150
# (and on Shmuelof) without having looked at them.
S=/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad; V=$S/voices; T=$S/space_test; R=/home/claude/dikduk-space
log() { echo "$(date +%H:%M) $*" >> $V/chain.log; }
if pgrep -f "exam_voice.py|train_head2.py|perek_to_manifest.py" > /dev/null; then echo "busy:"; pgrep -af "exam_voice.py|train_head2.py|perek_to_manifest.py" | cut -c1-160; exit 2; fi
ex() { [ -f $V/exam_$1.json ]; }                                   # a server exam finished (its .json is written at the end)
zx() { grep -A1 "vowel ear on held-out zami" $T/zami_$1.log 2>/dev/null | grep -q "the live rule"; }   # a head's own exams of Zami finished
p1() { grep -q "planned stop after epoch 3" $T/train_full_$1.log 2>/dev/null || [ -f $T/full_head_$1.pt ]; }
zami() {   # zami <name> <head>: an existing head's own exams (EPOCHS 0); Zami examined on all his pesukim (none of these heads heard him)
  cd $T && env HF_HOME=$S/hf HEAD_NV=1 HEAD_QUICK=1 HEAD_NV_SKIP=zami DK_VOWELS=$R/vowels.py python3 train_head2.py full 0 $2 > $T/zami_$1.log 2>&1
  log "queue: zami $1: $(grep -A1 'vowel ear on held-out zami' $T/zami_$1.log | grep -o 'words with a note.*' | cut -c1-150)"
}
zsplit() {   # zsplit <name> <head>: an existing head's exam of Zami split by recording (his archive Torah: nv4-nv6 trained on it; batch 2's aliyot: only nv6)
  cd $T && env HF_HOME=$S/hf HEAD_NV=1 HEAD_QUICK=1 HEAD_NV_SKIP=zami HEAD_NV_SPLIT=zami DK_VOWELS=$R/vowels.py python3 train_head2.py full 0 $2 > $T/zsplit_$1.log 2>&1
  log "queue: zami split $1: archive $(grep -A1 'zami split, archive' $T/zsplit_$1.log | grep -o 'words with a note.*' | cut -c1-120) | other $(grep -A1 'zami split, the other' $T/zsplit_$1.log | grep -o 'words with a note.*' | cut -c1-120)"
}
zs() { grep -A1 "zami split, the other" $T/zsplit_$1.log 2>/dev/null | grep -q "the live rule"; }
daya56() {   # Daya's Tehillim (Miqra, 4 perakim, 90 pesukim; a recording the letter head hears poorly: 15% clean) through the v5.6 server, RAW
  curl -s -m 10 http://127.0.0.1:7861/health | grep -q '"version":5.6' || { log "queue: daya_v56 not run: the dev server is not on 5.6"; exit 1; }
  cd /home/claude && RAW=1 DK_REPO=/home/claude/dikduk-v56 HF_HOME=$S/hf python3 -I $V/exam_voice.py $V/out_daya/align "$S/data_miqra/daya/{n:03d}.mp3" daya_v56 150 7 > $V/big/exam_daya_v56.log 2>&1
  log "big: exam daya_v56: $(grep -m1 '^== ' $V/big/exam_daya_v56.log)"
}
train() {  # train <name> <stop after epoch, 0 = to the end> [alignment floor]: nv6's recipe with Zami left out
  cd $T && env HF_HOME=$S/hf HEAD_RESUME=1 HEAD_STOP_AFTER=$2 HEAD_NV=1 HEAD_AL_FULL=2 HEAD_LR=3e-4 HEAD_NV_SKIP=zami ${3:+HEAD_NV_SKEL=$3} \
    HEAD_QUICK=1 DK_VOWELS=$R/vowels.py HEAD_OUT=$T/full_head_$1.pt python3 train_head2.py full 5 $T/full_head_alouf.pt >> $T/train_full_$1.log 2>&1
  if [ -f $T/full_head_$1.pt ]; then log "queue: $1 trained: $(grep -A1 'vowel ear on held-out zami' $T/train_full_$1.log | grep -o 'words with a note.*' | cut -c1-150)"
  else log "queue: $1: $(grep -E '^epoch|^planned stop|Error' $T/train_full_$1.log | tail -1 | cut -c1-80)"; fi
}
samra_man() {   # Faraj's own training items for the calibration test: perakim 1-10 only (the calibrated head is judged on 56-150), in a manifest of their own that no other run reads
  cd $V && env DK_LAB_MAN=$T/manifest_samra.jsonl HF_HOME=$S/hf python3 perek_to_manifest.py samra $(for n in 1 2 4 5 6 8 9 10; do printf "%s " "$S/data_samra/$(printf %03d $n).mp3:$n"; done) > $V/big/samra_man.log 2>&1 && touch $T/manifest_samra.done
  log "queue: samra_man: $(grep -c . $T/manifest_samra.jsonl 2>/dev/null) items; $(tail -n 1 $V/big/samra_man.log | cut -c1-100)"
}
calhead() {   # LAB_NOTES §32's cal30 on Faraj: 30 of his pesukim (x5) + 300 of Rabbi Alouf's, 6 epochs from the shipped head
  cd $T && env HF_HOME=$S/hf HEAD_MAN_EXTRA=$T/manifest_samra.jsonl HEAD_QUICK=1 HEAD_NV=5 HEAD_NV_KEEP=samra:30 HEAD_AL_SUB=300 HEAD_LR=3e-4 \
    HEAD_OUT=$T/full_head_cal_samra30.pt python3 train_head2.py full 6 $R/full_head.pt > $T/train_full_cal_samra30.log 2>&1
  log "queue: cal head samra30: $( [ -f $T/full_head_cal_samra30.pt ] && echo trained || echo "FAILED: $(tail -n 1 $T/train_full_cal_samra30.log | cut -c1-80)")"
}
calhead10() {   # §32's K=10 on Faraj: his first 10 pesukim of the same manifest (x10) + 300 of Rabbi Alouf's, 6 epochs from the shipped head
  cd $T && env HF_HOME=$S/hf HEAD_MAN_EXTRA=$T/manifest_samra.jsonl HEAD_QUICK=1 HEAD_NV=10 HEAD_NV_KEEP=samra:10 HEAD_AL_SUB=300 HEAD_LR=3e-4 \
    HEAD_OUT=$T/full_head_cal_samra10.pt python3 train_head2.py full 6 $R/full_head.pt > $T/train_full_cal_samra10.log 2>&1
  log "queue: cal head samra10: $( [ -f $T/full_head_cal_samra10.pt ] && echo trained || echo "FAILED: $(tail -n 1 $T/train_full_cal_samra10.log | cut -c1-80)")"
}
shm_man() {   # Shmuelof's own training items for the calibration test: perakim 1-6 (minus the exam-held 3), judged on 7-124
  cd $V && env DK_LAB_MAN=$T/manifest_shmuelof.jsonl HF_HOME=$S/hf python3 perek_to_manifest.py shmuelof $(for n in 1 2 4 5 6; do printf "%s " "$S/data_shmuelof/hbofPsa_$(printf %03d $n).mp3:$n"; done) > $V/big/shm_man.log 2>&1 && touch $T/manifest_shmuelof.done
  log "queue: shm_man: $(grep -c . $T/manifest_shmuelof.jsonl 2>/dev/null) items; $(tail -n 1 $V/big/shm_man.log | cut -c1-100)"
}
shm_cal() {
  cd $T && env HF_HOME=$S/hf HEAD_MAN_EXTRA=$T/manifest_shmuelof.jsonl HEAD_QUICK=1 HEAD_NV=5 HEAD_NV_KEEP=shmuelof:30 HEAD_AL_SUB=300 HEAD_LR=3e-4 \
    HEAD_OUT=$T/full_head_cal_shmuelof30.pt python3 train_head2.py full 6 $R/full_head.pt > $T/train_full_cal_shmuelof30.log 2>&1
  log "queue: cal head shmuelof30: $( [ -f $T/full_head_cal_shmuelof30.pt ] && echo trained || echo "FAILED: $(tail -n 1 $T/train_full_cal_shmuelof30.log | cut -c1-80)")"
}
step() {   # step <done test> <command>: skip it if done, else run it and stop here
  eval "$1" && return 0
  log "queue: start: $2"; eval "$2"; exit 0
}
step "ex samra_bigA"        "bash $V/big/exam.sh samra_bigA samra 1-55"
step "zx nv4"               "zami nv4 $R/full_head.pt"
step "ex samra_bigie"       "bash $V/big/exam.sh samra_bigie samra 1-150 IE 500"
step "ex samra_bigB"        "bash $V/big/exam.sh samra_bigB samra 56-150"
# one planted mistake per pasuk (PLANT_ONE): a rule that weighs the rest of the take can be tested fairly on these
step "ex samra_oneie"       "PLANT_ONE=1 bash $V/big/exam.sh samra_oneie samra 1-150 IE 500"
step "ex samra_oneei"       "PLANT_ONE=1 bash $V/big/exam.sh samra_oneei samra 1-150 EI 500"
step "ex samra_oneea"       "PLANT_ONE=1 bash $V/big/exam.sh samra_oneea samra 1-150 EA 500"
step "ex samra_oneuo"       "PLANT_ONE=1 bash $V/big/exam.sh samra_oneuo samra 1-150 UO 500"
step "ex samra_oneou"       "PLANT_ONE=1 bash $V/big/exam.sh samra_oneou samra 1-150 OU 500"
step "ex samra_bigou"       "bash $V/big/exam.sh samra_bigou samra 1-150 OU 500"
step "ex samra_skip"        "bash $V/big/exam.sh samra_skip samra 1-150 SKIP 500"
step "ex samra_drops"       "ONLY_PS=$(cat $V/big/drops_ps.txt) bash $V/big/exam.sh samra_drops samra 1-150 '' 5000"
step "ex shmuelof_big"      "bash $V/big/exam.sh shmuelof_big shmuelof 1-150"
step "ex shmuelof_oneie"    "PLANT_ONE=1 bash $V/big/exam.sh shmuelof_oneie shmuelof 1-150 IE"
step "ex shmuelof_oneei"    "PLANT_ONE=1 bash $V/big/exam.sh shmuelof_oneei shmuelof 1-150 EI"
step "ex shmuelof_oneea"    "PLANT_ONE=1 bash $V/big/exam.sh shmuelof_oneea shmuelof 1-150 EA"
step "ex shmuelof_oneuo"    "PLANT_ONE=1 bash $V/big/exam.sh shmuelof_oneuo shmuelof 1-150 UO"
step "ex shmuelof_oneou"    "PLANT_ONE=1 bash $V/big/exam.sh shmuelof_oneou shmuelof 1-150 OU"
# a student's own voice (§32-33's cal30) on the big tests: Faraj's head calibrated on 30 of his pesukim (perakim 1-10),
# judged on 56-150 — his correct reading and the same sparse planted mistakes as above (ONLY_PS: the same takes)
CAL=$T/full_head_cal_samra30.pt
step "[ -f $T/manifest_samra.done ]"   "samra_man"
step "[ -f $CAL ]"                     "calhead"
step "ex samra_cal_B"       "HEAD_FULL=$CAL bash $V/big/exam.sh samra_cal_B samra 56-150"
step "ex samra_cal_oneie"   "ONLY_PS=$(cat $V/big/ps56_oneie.txt) PLANT_ONE=1 HEAD_FULL=$CAL bash $V/big/exam.sh samra_cal_oneie samra 1-150 IE 500"
step "ex samra_cal_oneei"   "ONLY_PS=$(cat $V/big/ps56_oneei.txt) PLANT_ONE=1 HEAD_FULL=$CAL bash $V/big/exam.sh samra_cal_oneei samra 1-150 EI 500"
step "ex samra_cal_oneea"   "ONLY_PS=$(cat $V/big/ps56_oneea.txt) PLANT_ONE=1 HEAD_FULL=$CAL bash $V/big/exam.sh samra_cal_oneea samra 1-150 EA 500"
step "ex samra_cal_oneuo"   "ONLY_PS=$(cat $V/big/ps56_oneuo.txt) PLANT_ONE=1 HEAD_FULL=$CAL bash $V/big/exam.sh samra_cal_oneuo samra 1-150 UO 500"
step "ex samra_cal_oneou"   "ONLY_PS=$(cat $V/big/ps56_oneou.txt) PLANT_ONE=1 HEAD_FULL=$CAL bash $V/big/exam.sh samra_cal_oneou samra 1-150 OU 500"
# v5.6 through its own server (the worktree's code: the furtive patah, the drop bar at 20), Faraj's correct reading:
# must match the replays of the v5.5 exams above take for take
W6="DK_SERVER_REPO=/home/claude/dikduk-v56 DK_VERSION=5.6"
step "ex samra_v56B"        "$W6 bash $V/big/exam.sh samra_v56B samra 56-150"
# the shipped head's i-for-e takes again, through v5.6 (samra_oneie kept no rule inputs, so its marks cannot be replayed)
step "ex samra_v56_oneie"   "ONLY_PS=$(cat $V/big/ps56_oneie.txt) PLANT_ONE=1 $W6 bash $V/big/exam.sh samra_v56_oneie samra 1-150 IE 500"
# Shmuelof: a skipped word (the drop bar on a second voice), and the same calibration test as Faraj's
step "ex shmuelof_skip"     "bash $V/big/exam.sh shmuelof_skip shmuelof 1-150 SKIP 500"
CALS=$T/full_head_cal_shmuelof30.pt
step "[ -f $T/manifest_shmuelof.done ]"   "shm_man"
step "[ -f $CALS ]"                       "shm_cal"
step "[ -f $V/big/ps7_shm_big.txt ]"      "cd $V/big && python3 pslist.py shmuelof_big 7 ps7_shm_big.txt && for k in oneie oneei oneea oneuo oneou; do python3 pslist.py shmuelof_\$k 7 ps7_shm_\$k.txt; done"
step "ex shmuelof_cal_big"   "ONLY_PS=$(cat $V/big/ps7_shm_big.txt 2>/dev/null) HEAD_FULL=$CALS bash $V/big/exam.sh shmuelof_cal_big shmuelof 1-150 '' 5000"
step "ex shmuelof_cal_oneie" "ONLY_PS=$(cat $V/big/ps7_shm_oneie.txt 2>/dev/null) PLANT_ONE=1 HEAD_FULL=$CALS bash $V/big/exam.sh shmuelof_cal_oneie shmuelof 1-150 IE"
step "ex shmuelof_cal_oneei" "ONLY_PS=$(cat $V/big/ps7_shm_oneei.txt 2>/dev/null) PLANT_ONE=1 HEAD_FULL=$CALS bash $V/big/exam.sh shmuelof_cal_oneei shmuelof 1-150 EI"
step "ex shmuelof_cal_oneea" "ONLY_PS=$(cat $V/big/ps7_shm_oneea.txt 2>/dev/null) PLANT_ONE=1 HEAD_FULL=$CALS bash $V/big/exam.sh shmuelof_cal_oneea shmuelof 1-150 EA"
step "ex shmuelof_cal_oneuo" "ONLY_PS=$(cat $V/big/ps7_shm_oneuo.txt 2>/dev/null) PLANT_ONE=1 HEAD_FULL=$CALS bash $V/big/exam.sh shmuelof_cal_oneuo shmuelof 1-150 UO"
step "ex shmuelof_cal_oneou" "ONLY_PS=$(cat $V/big/ps7_shm_oneou.txt 2>/dev/null) PLANT_ONE=1 HEAD_FULL=$CALS bash $V/big/exam.sh shmuelof_cal_oneou shmuelof 1-150 OU"
# how short can a student's enrollment be? §32's K=10 (x10) on Faraj, judged like cal30 above, through v5.6
CAL10=$T/full_head_cal_samra10.pt
step "[ -f $CAL10 ]"                   "calhead10"
step "ex samra_cal10_B"     "HEAD_FULL=$CAL10 $W6 bash $V/big/exam.sh samra_cal10_B samra 56-150"
step "ex samra_cal10_oneei" "ONLY_PS=$(cat $V/big/ps56_oneei.txt) PLANT_ONE=1 HEAD_FULL=$CAL10 $W6 bash $V/big/exam.sh samra_cal10_oneei samra 1-150 EI 500"
step "ex samra_cal10_oneea" "ONLY_PS=$(cat $V/big/ps56_oneea.txt) PLANT_ONE=1 HEAD_FULL=$CAL10 $W6 bash $V/big/exam.sh samra_cal10_oneea samra 1-150 EA 500"
step "ex samra_cal10_oneie" "ONLY_PS=$(cat $V/big/ps56_oneie.txt) PLANT_ONE=1 HEAD_FULL=$CAL10 $W6 bash $V/big/exam.sh samra_cal10_oneie samra 1-150 IE 500"
step "ex samra_cal10_oneou" "ONLY_PS=$(cat $V/big/ps56_oneou.txt) PLANT_ONE=1 HEAD_FULL=$CAL10 $W6 bash $V/big/exam.sh samra_cal10_oneou samra 1-150 OU 500"
step "ex samra_cal10_oneuo" "ONLY_PS=$(cat $V/big/ps56_oneuo.txt) PLANT_ONE=1 HEAD_FULL=$CAL10 $W6 bash $V/big/exam.sh samra_cal10_oneuo samra 1-150 UO 500"
# a phone in a room (exam_voice.py DEGRADE=phone: a small room's early echoes, pink noise 20 dB under the singing, Opus at
# 24 kbps), the shipped head through v5.6: the planted e-for-i and o-for-u takes, then his correct reading 56-150
step "ex samra_phone_oneei" "ONLY_PS=$(cat $V/big/ps56_oneei.txt) PLANT_ONE=1 DEGRADE=phone $W6 bash $V/big/exam.sh samra_phone_oneei samra 1-150 EI 500"
step "ex samra_phone_oneou" "ONLY_PS=$(cat $V/big/ps56_oneou.txt) PLANT_ONE=1 DEGRADE=phone $W6 bash $V/big/exam.sh samra_phone_oneou samra 1-150 OU 500"
# which part of the phone costs the clean takes (on the phone a third of the clean takes went under the head-median bar
# of .7, and a take that is not clean gets no vowel notes): the 234 takes of the e-for-i list read correctly, the whole
# phone, then each part alone, then the phone at 64 kbps
PS56=$(cat $V/big/ps56_oneei.txt)
step "ex samra_dg_phone"    "ONLY_PS=$PS56 DEGRADE=phone $W6 bash $V/big/exam.sh samra_dg_phone samra 1-150 '' 500"
step "ex samra_dg_codec"    "ONLY_PS=$PS56 DEGRADE=kbps=24 $W6 bash $V/big/exam.sh samra_dg_codec samra 1-150 '' 500"
step "ex samra_dg_noise"    "ONLY_PS=$PS56 DEGRADE=snr=20 $W6 bash $V/big/exam.sh samra_dg_noise samra 1-150 '' 500"
step "ex samra_dg_room"     "ONLY_PS=$PS56 DEGRADE=room $W6 bash $V/big/exam.sh samra_dg_room samra 1-150 '' 500"
step "ex samra_dg_phone64"  "ONLY_PS=$PS56 DEGRADE=room,snr=20,kbps=64 $W6 bash $V/big/exam.sh samra_dg_phone64 samra 1-150 '' 500"
# the head trainings (the decision-making exams first)
step "zx nv5"               "zami nv5 $T/full_head_nv5.pt"
step "p1 noZami"            "train noZami 3"
step "[ -f $T/full_head_noZami.pt ]"      "train noZami 0"
# what the heads do for Zami, recording by recording (the archive Torah nv4-nv6 heard, the aliyot only nv6 did)
step "zs nv4"               "zsplit nv4 $R/full_head.pt"
step "zs nv6"               "zsplit nv6 $T/full_head_nv6.pt"
step "zs noZami"            "zsplit noZami $T/full_head_noZami.pt"
# the phone on the second voice (his 369 takes from perek 7 on, read correctly, with the hazzan)
step "ex shmuelof_phone_big" "ONLY_PS=$(cat $V/big/ps7_shm_big.txt) DEGRADE=phone $W6 bash $V/big/exam.sh shmuelof_phone_big shmuelof 1-150 '' 5000"
# the clean bar's risk side with today's ear: Daya's Tehillim, kept raw (the gate replayed in big/cleanbar.py)
step "ex daya_v56"         "daya56"
# if time is left: noise 10 dB under (the planted e-for-i takes, and those pesukim read correctly), and v5.6 on 1-55
step "ex samra_noisy_oneei" "ONLY_PS=$PS56 PLANT_ONE=1 DEGRADE=noisy $W6 bash $V/big/exam.sh samra_noisy_oneei samra 1-150 EI 500"
step "ex samra_noisy_B"     "ONLY_PS=$PS56 DEGRADE=noisy $W6 bash $V/big/exam.sh samra_noisy_B samra 1-150 '' 500"
step "ex samra_v56A"        "$W6 bash $V/big/exam.sh samra_v56A samra 1-55"
step "p1 noZamiSkel"        "train noZamiSkel 3 0.6"
step "[ -f $T/full_head_noZamiSkel.pt ]"  "train noZamiSkel 0 0.6"
step "zs noZamiSkel"        "zsplit noZamiSkel $T/full_head_noZamiSkel.pt"
# last, if time is left: the phone on all of his 56-150 (the 234 takes above already show it)
step "ex samra_phone_B"     "DEGRADE=phone $W6 bash $V/big/exam.sh samra_phone_B samra 56-150"
log "queue: all done"; echo "all done"
