"""
The actual glue: user upload (VCF/bgen) -> PLINK 1.9 binary -> infer.sh ->
structured predictions. Every subprocess call is logged; nothing here talks
to the network at request time (models/SNP files are baked into the image
at build time -- see ops/scripts/fetch_zenodo_models.sh).
"""
import glob
import logging
import os
import subprocess

import pandas as pd

from worker.config import settings

logger = logging.getLogger("worker.pipeline")


class PipelineError(Exception):
    """Raised for any pipeline failure; message is safe to show to end users."""


def _run(cmd: list[str], cwd: str | None = None) -> None:
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("Command failed (%s): stdout=%s stderr=%s", cmd[0], proc.stdout[-4000:], proc.stderr[-4000:])
        raise PipelineError(f"Step '{os.path.basename(cmd[0])}' failed. See worker logs for job diagnostics.")
    logger.info(proc.stdout[-2000:])


def convert_vcf_to_plink(vcf_path: str, out_prefix: str) -> str:
    """PLINK 1.9: VCF (or VCF.GZ) -> .bed/.bim/.fam, with a missingness QC
    filter applied in the same pass (--geno drops SNPs missing in >10% of
    samples). Genotypes are expected to already be harmonized to GRCh38;
    the platform cannot re-map genome builds (see UI/README warning)."""
    _run(
        [
            settings.plink_path,
            "--vcf",
            vcf_path,
            "--geno",
            settings.geno_missingness_threshold,
            "--make-bed",
            "--out",
            out_prefix,
        ]
    )
    if not os.path.isfile(out_prefix + ".bed"):
        raise PipelineError("VCF could not be converted to PLINK format. Check that the file is a valid VCF.")
    return out_prefix


def convert_bgen_to_plink(bgen_path: str, sample_path: str, out_prefix: str) -> str:
    """PLINK2: bgen (+ .sample) -> .bed/.bim/.fam, QC filter in the same pass."""
    _run(
        [
            settings.plink2_path,
            "--bgen",
            bgen_path,
            "ref-first",
            "--sample",
            sample_path,
            "--geno",
            settings.geno_missingness_threshold,
            "--make-bed",
            "--out",
            out_prefix,
        ]
    )
    if not os.path.isfile(out_prefix + ".bed"):
        raise PipelineError("bgen could not be converted to PLINK format. Check the .bgen/.sample pair.")
    return out_prefix


def run_infer(plink_prefix: str, output_prefix: str) -> str:
    """Runs Dietnet_inference/infer.sh with the REAL argument order (the
    README's order is wrong -- verified against the script itself):

        bash infer.sh <plink_path> <dietnet_code_path> <dietnet_files_path> <plink_test_prefix> <output_name>
    """
    infer_script = os.path.join(settings.dietnet_code_path, "infer.sh")
    os.makedirs(os.path.dirname(output_prefix), exist_ok=True)
    _run(
        [
            "bash",
            infer_script,
            settings.plink_path,
            settings.dietnet_code_path,
            settings.dietnet_files_path,
            plink_prefix,
            output_prefix,
        ],
        cwd=os.path.dirname(output_prefix),
    )
    predictions_file = f"{output_prefix}_dietnet_predictions.txt"
    if not os.path.isfile(predictions_file):
        raise PipelineError("Inference completed without producing a predictions file.")
    return predictions_file


def get_snp_overlap(output_prefix: str) -> tuple[int, int]:
    """Reads the overlap infer.sh already computed rather than recomputing it:
    <output_prefix>_dietnetsnps_extractedsnps.txt (SNPs found in the query
    set) vs DN_SNPS/dietnet_snps.txt (full training SNP panel)."""
    extracted_file = f"{output_prefix}_dietnetsnps_extractedsnps.txt"
    panel_file = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dietnet_snps.txt")

    with open(extracted_file) as f:
        overlap_count = sum(1 for _ in f)
    with open(panel_file) as f:
        overlap_total = sum(1 for _ in f)

    return overlap_count, overlap_total


def parse_predictions(predictions_file: str) -> list[dict]:
    """Parses <output_prefix>_dietnet_predictions.txt (tab-delimited: sample,
    model1..model15 population calls, all_models summary) into JSON-able rows."""
    df = pd.read_csv(predictions_file, sep="\t")
    return df.to_dict(orient="records")


def cleanup_intermediate_files(output_prefix: str) -> None:
    """infer.sh already removes most large intermediates; this clears the
    remaining per-model .npz directory and the hdf5 dataset, keeping only
    the predictions file + SNP lists as the durable "results" artifact set."""
    hdf5_path = f"{output_prefix}.hdf5"
    if os.path.isfile(hdf5_path):
        os.remove(hdf5_path)
    results_by_model_dir = f"{output_prefix}_DIETNET_RESULTS_BY_MODEL"
    for npz in glob.glob(os.path.join(results_by_model_dir, "*.npz")):
        os.remove(npz)
