"""Runs the worker's own pipeline steps (same order as tasks.run_inference_job,
minus DB/email) on one PLINK dataset. Usage: worker_driver.py <dataset> <workdir>"""
import os
import shutil
import sys

from worker import pipeline as p
from worker.config import settings

ds, wd = sys.argv[1], sys.argv[2]
shutil.rmtree(wd, ignore_errors=True)
os.makedirs(os.path.join(wd, "converted"))
os.makedirs(os.path.join(wd, "results"))
conv = os.path.join(wd, "converted", "query")
dummy = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dummy.bim")
try:
    p.requalify_plink(f"/data/{ds}", conv)
    relabel = p.relabel_snp_ids(conv, dummy)
    print("relabel:", relabel)
    pre = os.path.join(wd, "converted", "preflight_overlap")
    count, total = p.check_snp_overlap(conv, pre)
    print("overlap:", count, "of", total)
    if count < settings.min_reliable_snp_overlap:
        raise p.PipelineError(f"low overlap {count}")
    h = p.check_allele_harmonization(pre + ".bim", dummy)
    bad = h["swapped"] + h["flipped"] + h["ambiguous"]
    print("harmonization:", h)
    if h["compared"] and bad / h["compared"] > settings.max_allele_mismatch_fraction:
        raise p.PipelineError(f"allele mismatch {bad / h['compared']:.0%}")
    rates = p.compute_sample_missing_rates(pre, os.path.join(wd, "converted", "sample_missing"))
    out = os.path.join(wd, "results", "result")
    r = p.run_infer(conv, out)
    rows = p.build_results_table(r.by_model_file, rates, settings.consensus_threshold)
    p.write_results_table(out + "_results_table.tsv", rows)
    print("QC accuracy continent/pop:", r.qc_continent_accuracy, r.qc_population_accuracy)
    print("missing optional outputs:", r.missing_optional_outputs)
    truth = dict(line.split() for line in open(f"/data/{ds.replace('_minorA1', '')}.truth"))
    ok = sum(row["Population consensus"] == truth[row["Sample"]] for row in rows)
    print(f"rows: {len(rows)}; population consensus correct: {ok}/{len(rows)}; "
          f"continent NA: {sum(row['Continent consensus'] == 'NA' for row in rows)}")
    print("OUTCOME: success")
except p.QualityControlError as e:
    print("OUTCOME: QC rejection ->", e)
except p.PipelineError as e:
    print("OUTCOME: rejected ->", e)
print("results dir:", sorted(os.listdir(os.path.join(wd, "results"))))
