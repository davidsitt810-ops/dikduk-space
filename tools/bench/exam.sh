#!/bin/bash
# One exam of a never-heard reader through the dev server (127.0.0.1:7861), kept raw (RAW=1) so that bench/replay.py
# can replay the vowel notes, the planted mistakes and the gates offline. His correct reading, with the hazzan.
# usage: exam.sh <lab> <reader> <name> <perakim> [-|phone|noisy|<DEGRADE parts>] [K=V ...]
#   e.g. exam.sh $LAB samra samra_phone 56-150 phone            (every take of perakim 56-150 as a phone sends it)
#        exam.sh $LAB samra samra_ei 56-150 - PLANT=EI PLANT_ONE=1 NO_REF=1 N=40     (a planted run, to check a replay)
# A run that was stopped goes on where it ended (exam_<name>.jsonl). Reads <lab>/out_<reader>/align and
# <lab>/data_<reader>/NNN.mp3; writes <lab>/v/exam_<name>.json and .log.
LAB=${1:?lab}; WHO=${2:?reader}; NAME=${3:?name}; P=${4:?perakim}; DG=${5:--}; shift; shift; shift; shift; [ $# -gt 0 ] && shift
R=$(cd "$(dirname "$0")/../.." && pwd); mkdir -p "$LAB/v"; N=5000
for kv in "$@"; do case $kv in N=*) N=${kv#N=};; esac; done
curl -s -m 10 http://127.0.0.1:7861/health | grep -q '"version"' || { echo "exam $NAME not run: the dev server is not up"; exit 1; }
[ "$DG" != - ] && set -- "DEGRADE=$DG" "$@"
env DK_LAB="$LAB" DK_LAB_V="$LAB/v" DK_REPO="$R" RAW=1 PERAKIM="$P" "$@" python3 "$R/tools/exam_voice.py" "$LAB/out_$WHO/align" "$LAB/data_$WHO/{n:03d}.mp3" "$NAME" "$N" 7 > "$LAB/v/exam_$NAME.log" 2>&1
echo "$(date +%H:%M) exam $NAME: $(grep -m1 '^== ' "$LAB/v/exam_$NAME.log" || tail -n 1 "$LAB/v/exam_$NAME.log")" | tee -a "$LAB/v/chain.log"
