#!/bin/bash
# Line up a never-heard reader's Tehillim, perek by perek (the phone ear only: the exams need the pesukim's times).
# usage: align.sh <lab dir> <reader> <file pattern with %03d>     e.g. align.sh $LAB samra "$LAB/data_samra/%03d.mp3"
# A perek already lined up is skipped, so a second run goes on where the first ended. Needs bench_index.py run first,
# <lab>/tehillim/{nikud.py, ctcutil.py}, and PY = the Python that has torch (default python3).
LAB=$1; WHO=$2; PAT=$3; R=$(cd "$(dirname "$0")/../.." && pwd); OUT=$LAB/out_$WHO; mkdir -p $OUT/align
jobs=""; for n in $(seq 1 150); do [ -f $OUT/align/$n.json ] && continue; f=$(printf "$PAT" $n); [ -f "$f" ] && jobs="$jobs $f:$n"; done
[ -z "$jobs" ] && { echo "nothing to line up in $OUT"; exit 0; }
echo "lining up $(echo $jobs | wc -w) perakim in $OUT"
cd /tmp && AR= THREADS=${THREADS:-2} DK_LAB_CODE=$LAB/tehillim ${PY:-python3} $R/tools/voice_register.py $OUT $jobs >> $OUT/run.log 2>&1
echo "$(ls $OUT/align | wc -l) perakim lined up in $OUT"
