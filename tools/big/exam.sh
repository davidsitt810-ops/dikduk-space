#!/bin/bash
# Bigger tests, step 2: a never-heard reader's pesukim through the dev server (v5.5, the shipped heads), in planned parts
# that each end inside the 2-hour limit. usage: exam.sh <name> <samra|shmuelof> <perakim> [OU|IE|EI|EA|UO|SKIP] [max takes]
S=/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad; V=$S/voices
NAME=$1; WHO=$2; P=$3; PL=${4:-}; N=${5:-5000}
log() { echo "$(date +%H:%M) $*" >> $V/chain.log; }
case $WHO in
  samra) AL=$V/out_samra/align; SRC="$S/data_samra/{n:03d}.mp3";;
  shmuelof) AL=$V/out_shmuelof/align; SRC="$S/data_shmuelof/hbofPsa_{n:03d}.mp3";;
esac
# the dev server on the shipped heads (started if the machine was restarted); no server, no exam
FULL=${HEAD_FULL:-/home/claude/dikduk-space/full_head.pt}   # HEAD_FULL=<.pt>: another vowel head (a calibrated one)
bash $V/server_with.sh $FULL /home/claude/dikduk-space/letter_head.pt server_$(basename $FULL .pt) > /dev/null 2>&1
VER=${DK_VERSION:-5.5}; export DK_REPO=${DK_SERVER_REPO:-/home/claude/dikduk-space}   # the v5.6 worktree's code: its server, and its rule.py for the page's marks
curl -s -m 10 http://127.0.0.1:7861/health | grep -q "\"version\":$VER" || { log "big: exam $NAME not run: the dev server is not up on $VER"; exit 1; }
cd /home/claude
if [ "$PL" = SKIP ]; then RAW=1 PLANT=SKIP PERAKIM=$P HF_HOME=$S/hf python3 -I $V/exam_voice.py $AL "$SRC" $NAME $N 7 > $V/big/exam_$NAME.log 2>&1   # a skipped word: the hazzan kept
elif [ -n "$PL" ]; then RAW=1 PLANT=$PL NO_REF=1 PERAKIM=$P HF_HOME=$S/hf python3 -I $V/exam_voice.py $AL "$SRC" $NAME $N 7 > $V/big/exam_$NAME.log 2>&1
else RAW=1 PERAKIM=$P HF_HOME=$S/hf python3 -I $V/exam_voice.py $AL "$SRC" $NAME $N 7 > $V/big/exam_$NAME.log 2>&1; fi
log "big: exam $NAME: $(grep -m1 '^== ' $V/big/exam_$NAME.log)"
