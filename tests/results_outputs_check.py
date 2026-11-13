#!/usr/bin/env python3
"""Checks the new result outputs on an already-"done" job (the positive
control from preflight_checks.py --case positive --json-out):

  - POST /jobs/{id}/download with a password returns an AES-encrypted zip
    that opens with that password and not with a wrong one
  - GET (the old unencrypted route) and a too-short password are refused
  - the zip contains the results table and the job log next to infer.sh's
    usual outputs
  - the results table has the specifications.docx columns, one row per
    sample, consistent vote counts and consensus labels, and missing rates
  - the job log reports SNP totals/overlap and the consensus threshold
  - GET /jobs/{id} returns the same table rows in `predictions`

Needs pyzipper on the host (tests/run_all.sh runs this with tests/.venv).

Usage: results_outputs_check.py --base-url URL --job-id ID --access-token TOKEN
       [--consensus-threshold 12] [--expected-samples 2504] [--work-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys

import pyzipper

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ZIP_PASSWORD, get_job, session_from_access_token  # noqa: E402

CONTINENTS = ["EUR", "AFR", "SAS", "EAS", "AMR"]
POPULATIONS_BY_CONTINENT = {
    "AFR": ["YRI", "ESN", "GWD", "LWK", "MSL", "ACB", "ASW"],
    "EUR": ["IBS", "CEUGBR", "TSI", "FIN"],
    "SAS": ["PJL", "BEB", "GIH", "STUITU"],
    "EAS": ["CHB", "CHS", "CDX", "KHV", "JPT"],
    "AMR": ["MXL", "CLM", "PEL", "PUR"],
}
POPULATIONS = [p for pops in POPULATIONS_BY_CONTINENT.values() for p in pops]
EXPECTED_COLUMNS = ["Sample", "Missing rate (%)", "Continent consensus", "Population consensus"] + CONTINENTS + POPULATIONS

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  [{'ok' if condition else 'FAIL'}] {message}")
    if not condition:
        failures.append(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--access-token", required=True)
    parser.add_argument("--consensus-threshold", type=int, default=12)
    parser.add_argument("--expected-samples", type=int, default=2504)
    parser.add_argument("--work-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp"))
    args = parser.parse_args()
    os.makedirs(args.work_dir, exist_ok=True)

    session = session_from_access_token(args.base_url, args.access_token)
    url = f"{args.base_url}/jobs/{args.job_id}/download"

    print("Download endpoint:")
    r = session.get(url, timeout=60)
    check(r.status_code == 405, f"GET (old unencrypted route) refused: {r.status_code}")
    r = session.post(url, json={"password": "short"}, timeout=60)
    check(r.status_code == 422, f"7-char-or-less password refused: {r.status_code}")
    r = session.post(url, json={}, timeout=60)
    check(r.status_code == 422, f"missing password refused: {r.status_code}")
    r = session.post(url, json={"password": ZIP_PASSWORD}, timeout=300)
    check(r.status_code == 200 and r.headers.get("content-type") == "application/zip", f"POST with password: {r.status_code}")
    if r.status_code != 200:
        print("[FAIL] results_outputs: could not download the zip")
        sys.exit(1)
    zip_path = os.path.join(args.work_dir, f"{args.job_id}_results.zip")
    with open(zip_path, "wb") as f:
        f.write(r.content)
    print(f"  zip saved to {zip_path} ({len(r.content) / 1e6:.1f} MB)")

    print("Encryption:")
    with pyzipper.AESZipFile(zip_path) as zf:
        infos = zf.infolist()
        check(
            all(i.flag_bits & 0x1 and getattr(i, "wz_aes_strength", None) == 3 for i in infos),
            f"all {len(infos)} entries AES-256 encrypted",
        )
        zf.setpassword(b"definitely-wrong")
        try:
            zf.read("result_job_log.txt")
            check(False, "wrong password rejected")
        except RuntimeError:
            check(True, "wrong password rejected")

        zf.setpassword(ZIP_PASSWORD.encode())
        names = set(zf.namelist())
        print("Zip contents:")
        for name in sorted(n for n in names if "/" not in n):
            print(f"    {name}")
        per_model = [n for n in names if n.startswith("result_DIETNET_RESULTS_BY_MODEL/")]
        print(f"    result_DIETNET_RESULTS_BY_MODEL/ ({len(per_model)} files)")
        for expected in [
            "result_results_table.tsv",
            "result_job_log.txt",
            "result_dietnet_predictions.txt",
            "result_dietnetsnps_extractedsnps.txt",
            "result_dietnetsnps_notextractedsnps.txt",
            "result.hdf5",
        ]:
            check(expected in names, f"zip contains {expected}")
        check(len(per_model) == 15, f"15 per-model .npz files ({len(per_model)})")

        table_text = zf.read("result_results_table.tsv").decode()
        log_text = zf.read("result_job_log.txt").decode()
        predictions_text = zf.read("result_dietnet_predictions.txt").decode()

    print("Results table:")
    reader = csv.DictReader(io.StringIO(table_text), delimiter="\t")
    check(reader.fieldnames == EXPECTED_COLUMNS, "columns match specifications.docx order")
    rows = list(reader)
    check(len(rows) == args.expected_samples, f"{len(rows)} rows (expected {args.expected_samples})")

    model_votes = {r["samples"]: r for r in csv.DictReader(io.StringIO(predictions_text), delimiter="\t")}
    bad_sums = bad_consensus = bad_votes = bad_rate = 0
    for row in rows:
        pop_counts = {p: int(row[p]) for p in POPULATIONS}
        cont_counts = {c: int(row[c]) for c in CONTINENTS}
        if sum(pop_counts.values()) != 15 or sum(cont_counts.values()) != 15:
            bad_sums += 1
        if any(cont_counts[c] != sum(pop_counts[p] for p in POPULATIONS_BY_CONTINENT[c]) for c in CONTINENTS):
            bad_sums += 1
        # Recount from the raw 15 model columns of infer.sh's own predictions file.
        raw = model_votes.get(row["Sample"])
        if raw is None or any(
            pop_counts[p] != [raw[f"model{i}"] for i in range(1, 16)].count(p) for p in POPULATIONS
        ):
            bad_votes += 1
        for counts, column in ((pop_counts, "Population consensus"), (cont_counts, "Continent consensus")):
            label, votes = max(counts.items(), key=lambda kv: kv[1])
            expected = label if votes >= args.consensus_threshold else "NA"
            if row[column] != expected:
                bad_consensus += 1
        try:
            if not 0.0 <= float(row["Missing rate (%)"]) <= 100.0:
                bad_rate += 1
        except ValueError:
            bad_rate += 1
    check(bad_sums == 0, f"vote counts sum to 15 and continents = sum of their populations ({bad_sums} bad)")
    check(bad_votes == 0, f"population counts match the raw model1..model15 columns ({bad_votes} bad)")
    check(bad_consensus == 0, f"consensus = label with >= {args.consensus_threshold}/15 votes, else NA ({bad_consensus} bad)")
    check(bad_rate == 0, f"missing rate is a number in [0, 100] for every sample ({bad_rate} bad)")

    n_cont = sum(r["Continent consensus"] != "NA" for r in rows)
    n_pop = sum(r["Population consensus"] != "NA" for r in rows)
    rates = [float(r["Missing rate (%)"]) for r in rows]
    print(f"  continent consensus reached for {n_cont}/{len(rows)} samples; population consensus for {n_pop}/{len(rows)}")
    print(f"  missing rate: mean {sum(rates) / len(rates):.3f}%, max {max(rates):.3f}%")
    print("  first 3 rows (first 9 columns):")
    for row in rows[:3]:
        print("    " + " | ".join(str(row[c]) for c in EXPECTED_COLUMNS[:9]))

    print("Job log:")
    for expected in [
        "Overlap by position:",
        "Overlap by ID:",
        "Overlap by alleles:",
        "Diet Network panel:      229986",
        "SNP ID relabeling",
        "Allele harmonization",
        f"Consensus threshold: {args.consensus_threshold} of 15 models",
        f"Continent consensus reached:  {n_cont} of {len(rows)} samples",
        f"Population consensus reached: {n_pop} of {len(rows)} samples",
        "infer.sh output",
        "Inference with Dietnet completed",
    ]:
        check(expected in log_text, f"log contains {expected!r}")
    print("  --- log (first 40 lines) ---")
    for line in log_text.splitlines()[:40]:
        print(f"  | {line}")

    print("API:")
    job = get_job(session, args.base_url, args.job_id)
    preds = job.get("predictions") or {}
    check(preds.get("consensus_threshold") == args.consensus_threshold, "predictions.consensus_threshold set")
    api_rows = preds.get("rows") or []
    check(len(api_rows) == len(rows), f"predictions.rows has {len(api_rows)} rows")
    if api_rows:
        first = api_rows[0]
        check(
            str(first["Sample"]) == rows[0]["Sample"]
            and first["Population consensus"] == rows[0]["Population consensus"],
            "API rows match the table file",
        )

    if failures:
        print(f"[FAIL] results_outputs: {len(failures)} check(s) failed")
        sys.exit(1)
    print("[PASS] results_outputs: encrypted zip, results table, job log and API predictions all as expected")


if __name__ == "__main__":
    main()
