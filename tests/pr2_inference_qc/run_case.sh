#!/bin/bash
# Runs inside the container. Usage: run_case.sh <case> <dataset> <folds> <reps>
# /code = PR's Dietnet_inference (ro), /files = model+1KGP files (ro),
# /data = generated datasets (ro), /runs = writable output.
case=$1; ds=$2; folds=$3; reps=$4
wd=/runs/$case
rm -rf "$wd"; mkdir -p "$wd/input"; cd "$wd"
cp /data/$ds.bed /data/$ds.bim /data/$ds.fam input/
cp input/$ds.bim input_bim_before.txt
start=$(date +%s)
bash /code/infer.sh /opt/plink/plink /code /files "$wd/input/$ds" "$case" "$folds" "$reps" > infer.log 2>&1
rc=$?
echo "case=$case exit=$rc seconds=$(( $(date +%s) - start ))"
ls -1 "$wd" | sed 's/^/  /'
