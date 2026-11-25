#!/bin/bash
# Keep the bench's costly parts somewhere that outlives the machine: the readers' alignments (an hour of computing
# each) and the exams' kept answers (hours). The first bench was lost with its machine on Nov 25.
# usage: save.sh <lab> <dest folder>       restore: untar align_<reader>.tgz into <lab>/, gunzip the exams into <lab>/v/
LAB=${1:?lab}; D=${2:?where to keep it}; mkdir -p "$D/v"
for a in "$LAB"/out_*/align; do [ -d "$a" ] || continue; w=$(basename "$(dirname "$a")"); tar czf "$D/align_${w#out_}.tgz.part" -C "$LAB" "$w/align" && mv "$D/align_${w#out_}.tgz.part" "$D/align_${w#out_}.tgz"; done
for f in "$LAB"/v/exam_*.full.jsonl; do [ -f "$f" ] || continue; g="$D/v/$(basename "$f").gz"; [ "$g" -nt "$f" ] || { gzip -c "$f" > "$g.part" && mv "$g.part" "$g"; }; done
for f in "$LAB"/v/exam_*.json "$LAB"/v/exam_*.log "$LAB"/v/chain.log; do [ -f "$f" ] && cp -u "$f" "$D/v/"; done
echo "kept in $D: $(ls "$D" | grep -c tgz) alignments, $(ls "$D/v" | grep -c 'full.jsonl.gz') exams with the whole answers, $(du -sh "$D" | cut -f1)"
