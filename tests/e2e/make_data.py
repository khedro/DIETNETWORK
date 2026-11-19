#!/usr/bin/env python3
"""Generates one non-overlapping 50-sample upload per simulated user from the
dataTest 1000G trio, in that user's format. Non-overlapping so a results table
containing another user's samples is detectable.

Runs inside the worker image (needs plink 1.9 and plink2). See run.sh.

Usage: make_data.py SRC_PREFIX LOW_OVERLAP_BIM OUT_DIR
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys

PLINK = "/opt/plink/plink"
PLINK2 = "/opt/plink2/plink2"
SAMPLES_PER_USER = 50
SEED = 2026

# user -> (format, how the browser selects the files, expected outcome)
USERS = {
    "user1": ("plink", "together", "done"),
    "user2": ("plink", "together", "done"),
    "user3": ("plink", "together", "done"),
    "user4": ("plink", "dropped", "done"),
    "user5": ("plink", "separate", "done"),
    "user6": ("plink", "separate", "done"),
    "user7": ("plink", "separate", "done"),
    "user8": ("vcf", "single", "done"),
    "user9": ("vcf.gz", "single", "done"),
    "user10": ("bgen", "single", "done"),
    "user11": ("bgen", "single", "done"),
    "user12": ("low_overlap", "separate", "failed"),
}


def run(*cmd: str) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")


def main() -> None:
    src, low_overlap_bim, out_dir = sys.argv[1:4]
    with open(src + ".fam") as f:
        samples = [line.split()[:2] for line in f]
    random.Random(SEED).shuffle(samples)

    expected = {}
    for i, (user, (fmt, selection, outcome)) in enumerate(USERS.items()):
        chosen = samples[i * SAMPLES_PER_USER : (i + 1) * SAMPLES_PER_USER]
        user_dir = os.path.join(out_dir, user)
        os.makedirs(user_dir, exist_ok=True)
        keep = os.path.join(user_dir, "keep.txt")
        with open(keep, "w") as f:
            f.writelines(f"{fid} {iid}\n" for fid, iid in chosen)

        base = os.path.join(user_dir, "base")
        run(PLINK, "--bfile", src, "--keep", keep, "--real-ref-alleles", "--make-bed", "--out", base)

        prefix = os.path.join(user_dir, user)
        if fmt == "plink":
            run(PLINK, "--bfile", base, "--real-ref-alleles", "--make-bed", "--out", prefix)
            files = [prefix + ".bed", prefix + ".bim", prefix + ".fam"]
        elif fmt == "low_overlap":
            extract = os.path.join(user_dir, "extract.txt")
            with open(low_overlap_bim) as f, open(extract, "w") as g:
                g.writelines(line.split()[1] + "\n" for line in f)
            run(PLINK, "--bfile", base, "--extract", extract, "--real-ref-alleles", "--make-bed", "--out", prefix)
            files = [prefix + ".bed", prefix + ".bim", prefix + ".fam"]
        elif fmt == "vcf":
            run(PLINK, "--bfile", base, "--real-ref-alleles", "--recode", "vcf-iid", "--out", prefix)
            files = [prefix + ".vcf"]
        elif fmt == "vcf.gz":
            run(PLINK, "--bfile", base, "--real-ref-alleles", "--recode", "vcf-iid", "bgz", "--out", prefix)
            files = [prefix + ".vcf.gz"]
        elif fmt == "bgen":
            run(PLINK2, "--bfile", base, "--export", "bgen-1.2", "bits=8", "ref-first", "--out", prefix)
            files = [prefix + ".bgen", prefix + ".sample"]
        else:
            raise SystemExit(f"Unknown format {fmt}")

        expected[user] = {
            "format": fmt,
            "selection": selection,
            "outcome": outcome,
            "files": [os.path.relpath(p, out_dir) for p in files],
            "bytes": sum(os.path.getsize(p) for p in files),
            "samples": [iid for _, iid in chosen],
        }
        for name in os.listdir(user_dir):
            path = os.path.join(user_dir, name)
            if name.startswith("base") or name.endswith((".log", ".nosex")):
                os.remove(path)
        print(f"{user}: {fmt:11s} {expected[user]['bytes'] / 1e6:7.1f} MB  expected {outcome}", flush=True)

    with open(os.path.join(out_dir, "expected.json"), "w") as f:
        json.dump(expected, f, indent=1)


if __name__ == "__main__":
    main()
