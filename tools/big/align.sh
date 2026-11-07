#!/bin/bash
# Bigger tests, step 1: line up never-heard readers' Tehillim, perek by perek (phone ear only; the exam needs the pesukim's
# times, not the throat register). usage: align.sh <out dir> <data dir> <file pattern with {n}> <perakim...>
# Skips a perek already lined up, so a planned second run goes on where the first ended.
S=/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad; V=$S/voices; R=/home/claude/dikduk-space
OUT=$1; PAT=$2; shift 2
log() { echo "$(date +%H:%M) $*" >> $V/chain.log; }
jobs=""; for n in "$@"; do [ -f $OUT/align/$n.json ] && continue; f=$(printf "$PAT" $n); [ -f "$f" ] && jobs="$jobs $f:$n"; done
[ -z "$jobs" ] && { log "big: nothing to line up in $(basename $OUT)"; exit 0; }
log "big: lining up $(echo $jobs | wc -w) perakim in $(basename $OUT)"
cd /home/claude && HF_HOME=$S/hf AR= THREADS=2 python3 $R/tools/voice_register.py $OUT $jobs >> $OUT/run_big.log 2>&1
log "big: $(basename $OUT) now $(ls $OUT/align | wc -l) perakim lined up"
