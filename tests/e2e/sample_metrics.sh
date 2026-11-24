#!/usr/bin/env bash
# Samples per-container CPU/memory, host load, running model processes and /data
# size every few seconds until STOP_FILE appears. One CSV row per container per sample.
#
# Usage: sample_metrics.sh PROJECT OUT_CSV STOP_FILE [INTERVAL_SECONDS]
set -u
PROJECT="$1"
OUT="$2"
STOP="$3"
INTERVAL="${4:-5}"

echo "epoch,load1,inference_procs,infer_sh_procs,data_mb,container,cpu_pct,mem_usage" > "$OUT"
while [ ! -e "$STOP" ]; do
    now=$(date +%s)
    load1=$(cut -d' ' -f1 /proc/loadavg)
    top=$(docker top "${PROJECT}-worker-1" -eo pid,args 2>/dev/null)
    inference=$(printf '%s\n' "$top" | grep -c "inference.py")
    infer_sh=$(printf '%s\n' "$top" | grep -c "bash .*infer.sh")
    data_mb=$(docker exec "${PROJECT}-worker-1" du -sm /data 2>/dev/null | cut -f1)
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' 2>/dev/null \
        | grep "^${PROJECT}-" \
        | while IFS= read -r row; do
            echo "${now},${load1},${inference},${infer_sh},${data_mb:-0},${row}" >> "$OUT"
        done
    sleep "$INTERVAL"
done
