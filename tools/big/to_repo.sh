#!/bin/bash
# Copy the bigger tests' scripts into the v56 worktree's tools/big/ (LAB_NOTES §39 cites them). They read the exams
# (exam_<name>.json) from DK_LAB_V, or else from the folder above their own; the lab's paths stay as they were run.
S=/tmp/claude-0/-home-claude/13b8b04f-7b29-591b-ba7b-28708cdbf43a/scratchpad; B=$S/voices/big; W=/home/claude/dikduk-v56
mkdir -p $W/tools/big
for f in $B/*.py $B/*.sh $B/*.txt; do
  n=$(basename $f); [ "$n" = to_repo.sh ] && continue; case $n in *_results.txt) continue;; esac   # the run's own jottings stay out
  sed "s|os.path.dirname(os.path.dirname(os.path.abspath(__file__)))|(os.environ.get('DK_LAB_V') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))|" $f > $W/tools/big/$n
done
cp $B/to_repo.sh $W/tools/big/to_repo.sh
ls $W/tools/big | wc -l
