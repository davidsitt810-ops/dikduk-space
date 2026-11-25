#!/bin/bash
# Several exams one after the other, in one job that ends by itself before a time budget (a job stopped from outside
# cannot be told from a crash; an exam that was stopped goes on where it ended the next time).
# usage: chain.sh <lab> <reader> <minutes> <durable folder or -> <name>:<perakim>:<-|phone|noisy>[:N] ...
LAB=${1:?}; WHO=${2:?}; MIN=${3:?}; KEEP=${4:?}; shift 4; R=$(cd "$(dirname "$0")/../.." && pwd); END=$(( $(date +%s) + MIN * 60 ))
for spec in "$@"; do
  IFS=: read -r NAME P DG N <<< "$spec"; left=$(( END - $(date +%s) ))
  [ -f "$LAB/v/exam_$NAME.json" ] && { echo "exam $NAME: already done"; continue; }
  [ $left -lt 120 ] && { echo "out of time before $NAME"; break; }
  BUDGET_S=$left bash "$R/tools/bench/exam.sh" "$LAB" "$WHO" "$NAME" "$P" "$DG" ${N:+N=$N}
  [ -f "$LAB/v/exam_$NAME.json" ] || echo "exam $NAME: stopped at $(wc -l < "$LAB/v/exam_$NAME.jsonl" 2>/dev/null) takes (it goes on the next time)"
  [ "$KEEP" != - ] && bash "$R/tools/bench/save.sh" "$LAB" "$KEEP" | tail -1
done
