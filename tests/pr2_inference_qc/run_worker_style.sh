#!/bin/bash
# Mimics worker/worker/pipeline.py:run_infer -- the 5-argument call it makes today.
wd=/runs/worker5args
rm -rf "$wd"; mkdir -p "$wd/input"; cd "$wd"
cp /data/numeric.bed /data/numeric.bim /data/numeric.fam input/
bash /code/infer.sh /opt/plink/plink /code /files "$wd/input/numeric" job > infer.log 2>&1
echo "exit=$?"
echo "worker expects job_dietnet_predictions.txt: $( [ -f job_dietnet_predictions.txt ] && echo present || echo MISSING )"
grep -E "seq|error|Exit|usage" infer.log | head -8
