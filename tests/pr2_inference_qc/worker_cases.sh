#!/bin/bash
# Runs worker_driver.py for each dataset in parallel inside one container.
cd /app
for ds in numeric low full_minorA1 full; do
  python /j/worker_driver.py "$ds" "/runs/w_$ds" > "/runs/w_$ds.out" 2>&1 &
done
wait
for ds in numeric low full_minorA1 full; do echo "===== $ds"; grep -v "^\s*$" "/runs/w_$ds.out" | grep -vE "^(INFO|WARNING)" | tail -9; done
