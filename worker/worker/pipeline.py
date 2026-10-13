"""
The actual glue: user upload (VCF/bgen) -> PLINK 1.9 binary -> infer.sh ->
structured predictions. Every subprocess call is logged; nothing here talks
to the network at request time (models/SNP files are baked into the image
at build time -- see ops/scripts/fetch_zenodo_models.sh).
"""
import csv
import logging
import os
import subprocess

from worker.config import settings

logger = logging.getLogger("worker.pipeline")


class PipelineError(Exception):
    """Raised for any pipeline failure; message is safe to show to end users."""


def _run(cmd: list[str], cwd: str | None = None) -> str:
    """Runs cmd, raising PipelineError on a nonzero exit. Returns stdout so
    callers can keep it (run_infer puts infer.sh's output in the job log)."""
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("Command failed (%s): stdout=%s stderr=%s", cmd[0], proc.stdout[-4000:], proc.stderr[-4000:])
        raise PipelineError(f"Step '{os.path.basename(cmd[0])}' failed. See worker logs for job diagnostics.")
    logger.info(proc.stdout[-2000:])
    # infer.sh (Dietnet_inference/infer.sh, vendored model code) doesn't check
    # the exit code of any of the python steps it shells out to, so it can
    # exit 0 -- "succeeding" -- even when e.g. inference_dataset.py crashed
    # and no predictions were produced. Always surface stderr, not just on a
    # nonzero return code, or the real traceback never reaches the logs.
    if proc.stderr.strip():
        logger.warning("%s produced stderr despite exit 0: %s", cmd[0], proc.stderr[-4000:])
    return proc.stdout


def convert_vcf_to_plink(vcf_path: str, out_prefix: str) -> str:
    """PLINK 1.9: VCF (or VCF.GZ) -> .bed/.bim/.fam, with a missingness QC
    filter applied in the same pass (--geno drops SNPs missing in >10% of
    samples). Genotypes are expected to already be harmonized to GRCh38;
    the platform cannot re-map genome builds (see UI/README warning).

    --real-ref-alleles: without it, plink1.9's --make-bed default is to
    reassign A2 to whichever allele is major *in this sample*, silently
    discarding the VCF's own REF/ALT convention for any SNP where that
    differs from the reference panel's. check_allele_harmonization (run
    later, against this same converted file) would then see a spurious
    swap for every such SNP -- rejecting well-harmonized uploads as an
    artifact of this conversion step, not a real problem with the data."""
    _run(
        [
            settings.plink_path,
            "--vcf",
            vcf_path,
            "--real-ref-alleles",
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


def requalify_plink(in_prefix: str, out_prefix: str) -> str:
    """PLINK 1.9: already-PLINK .bed/.bim/.fam upload -> re-written .bed/.bim/.fam
    at a known location, with the same missingness QC filter applied as the
    VCF/bgen paths (--geno) so all three input types get identical
    filtering before infer.sh, rather than trusting the upload as-is.

    --real-ref-alleles: see convert_vcf_to_plink -- same plink1.9 default
    (reassign A2 to the sample's major allele) applies to --bfile input
    too, so without this flag a well-harmonized upload can come out of
    this *lossless* requalification pass with ~a quarter of its SNPs
    silently A1/A2-swapped relative to what the user actually uploaded."""
    _run(
        [
            settings.plink_path,
            "--bfile",
            in_prefix,
            "--real-ref-alleles",
            "--geno",
            settings.geno_missingness_threshold,
            "--make-bed",
            "--out",
            out_prefix,
        ]
    )
    if not os.path.isfile(out_prefix + ".bed"):
        raise PipelineError("Uploaded PLINK files could not be processed. Check that the .bed/.bim/.fam set is valid.")
    return out_prefix


def count_samples(plink_prefix: str) -> int:
    """Number of samples in a converted PLINK set (one line per sample in
    .fam). Checked right after conversion -- VCF/bgen sample counts aren't
    known before that point -- so an oversized upload is rejected before any
    PLINK/inference work is spent on it."""
    with open(plink_prefix + ".fam") as f:
        return sum(1 for _ in f)


def check_snp_overlap(plink_prefix: str, tmp_out_prefix: str) -> tuple[int, int]:
    """Fast pre-flight overlap check: runs the same '--extract dietnet_snps.txt'
    step infer.sh performs as its first stage, but *before* committing to the
    full 15-model ensemble. Lets a doomed-to-be-unreliable job (< 1000
    overlapping SNPs) be rejected immediately instead of after several
    minutes of inference. infer.sh redoes this extraction itself, so this is
    a small amount of duplicated (cheap) work in exchange for never running
    the ensemble on data we already know is unreliable."""
    panel_file = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dietnet_snps.txt")
    with open(panel_file) as f:
        overlap_total = sum(1 for _ in f)

    cmd = [
        settings.plink_path,
        "--bfile",
        plink_prefix,
        "--extract",
        panel_file,
        "--make-bed",
        "--real-ref-alleles",
        "--out",
        tmp_out_prefix,
    ]
    # Not using _run() here: unlike a low-but-nonzero overlap (which PLINK
    # completes normally, just with a small/empty .bim -- see below), PLINK
    # exits *non-zero* with "No variants remaining after --extract" when
    # the overlap is exactly zero. _run() would treat that as a hard
    # pipeline failure and hide it behind a generic error, instead of the
    # same "0 of N SNPs found" rejection (and chr-prefix-mismatch hint,
    # see detect_chr_prefix_mismatch) a low-overlap upload gets.
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if "No variants remaining after --extract" in proc.stderr:
            return 0, overlap_total
        logger.error("Command failed (%s): stdout=%s stderr=%s", cmd[0], proc.stdout[-4000:], proc.stderr[-4000:])
        raise PipelineError(f"Step '{os.path.basename(cmd[0])}' failed. See worker logs for job diagnostics.")
    logger.info(proc.stdout[-2000:])
    if proc.stderr.strip():
        logger.warning("%s produced stderr despite exit 0: %s", cmd[0], proc.stderr[-4000:])

    # Mirrors infer.sh's own check: PLINK can complete without producing a
    # .bim when there's no overlap at all, rather than exiting non-zero.
    if not os.path.isfile(tmp_out_prefix + ".bim"):
        return 0, overlap_total
    with open(tmp_out_prefix + ".bim") as f:
        overlap_count = sum(1 for _ in f)
    return overlap_count, overlap_total


def _normalize_chrom(chrom: str) -> str:
    return chrom[3:] if chrom.lower().startswith("chr") else chrom


def _read_bim_positions(bim_path: str) -> set[str]:
    """chrom:pos pairs from a .bim -- columns 1 and 4, which exist in every
    .bim regardless of what convention its ID column (2) uses. Unlike a SNP
    ID, chrom+pos is comparable across ID-naming schemes without needing to
    know which one either side used."""
    positions = set()
    with open(bim_path) as f:
        for line in f:
            fields = line.split()
            if len(fields) < 4:
                continue
            positions.add(f"{_normalize_chrom(fields[0])}:{fields[3]}")
    return positions


def detect_id_labeling_mismatch(plink_prefix: str) -> bool:
    """Cheap post-hoc diagnostic for a low-overlap rejection: pure string/set
    comparison, no extra plink invocation. Only called when check_snp_overlap
    already failed (see tasks.py), so it adds nothing to the normal/success
    path.

    check_snp_overlap's --extract matches on the SNP ID column (2) alone, so
    it's blind to a query using a different ID convention than the panel's
    "chr1:12345:A:G" -- e.g. no "chr" prefix, or rsIDs -- even when the
    underlying positions are identical. Comparing chrom+pos instead (see
    _read_bim_positions) is convention-agnostic: if that overlap is high
    while the raw ID overlap was low, the data matches and only the
    labeling differs -- not a genuine low-overlap/wrong-build dataset."""
    dummy_bim_path = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dummy.bim")
    panel_file = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dietnet_snps.txt")
    with open(panel_file) as f:
        panel_ids = {line.strip() for line in f}
    panel_positions = _read_bim_positions(dummy_bim_path)

    with open(plink_prefix + ".bim") as f:
        query_rows = [line.split() for line in f if line.strip()]
    query_ids = {row[1] for row in query_rows if len(row) > 1}
    query_positions = {f"{_normalize_chrom(row[0])}:{row[3]}" for row in query_rows if len(row) > 3}

    raw_overlap = len(query_ids & panel_ids)
    position_overlap = len(query_positions & panel_positions)

    # Only worth mentioning if comparing by position would have made a
    # material difference -- not just a handful of coincidental matches.
    return position_overlap >= settings.min_reliable_snp_overlap and position_overlap > raw_overlap * 2


_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}


def _complement(allele: str) -> str | None:
    """None for indels/multi-base alleles or missing ('0') codes -- strand
    complementing only makes sense for a single standard base."""
    return _COMPLEMENT.get(allele)


def _read_bim_alleles(bim_path: str) -> dict[str, tuple[str, str]]:
    alleles: dict[str, tuple[str, str]] = {}
    with open(bim_path) as f:
        for line in f:
            fields = line.split()
            if len(fields) < 6:
                continue
            snp_id, a1, a2 = fields[1], fields[4].upper(), fields[5].upper()
            alleles[snp_id] = (a1, a2)
    return alleles


def check_allele_harmonization(extracted_bim_path: str, dummy_bim_path: str) -> dict[str, int]:
    """Compares each overlapping SNP's alleles against the training panel's
    reference alleles (DN_SNPS/dummy.bim -- the one 1KGP sample infer.sh
    merges against, carrying the panel's canonical A1/A2). infer.sh runs
    PLINK with --real-ref-alleles, which tells it to trust the query's A1/A2
    as given rather than auto-flip by allele frequency -- so a systematically
    swapped or strand-flipped upload would otherwise silently invert the
    additive dosage for those SNPs instead of erroring.

    Returns counts by classification. 'ambiguous' covers A/T and C/G SNPs,
    where a strand flip and an allele-order swap produce the identical
    observed pair -- the two causes genuinely can't be told apart there."""
    query = _read_bim_alleles(extracted_bim_path)
    reference = _read_bim_alleles(dummy_bim_path)

    counts = {"compared": 0, "matched": 0, "swapped": 0, "flipped": 0, "ambiguous": 0, "mismatched": 0}
    for snp_id, (q1, q2) in query.items():
        ref = reference.get(snp_id)
        if ref is None:
            continue
        r1, r2 = ref
        if "0" in (q1, q2, r1, r2):
            continue  # missing/monomorphic allele code -- not a meaningful comparison

        counts["compared"] += 1
        if (q1, q2) == (r1, r2):
            counts["matched"] += 1
            continue

        c1, c2 = _complement(r1), _complement(r2)
        palindromic = c1 == r2 and c2 == r1  # A/T or C/G pair

        if (q1, q2) == (r2, r1):
            counts["ambiguous" if palindromic else "swapped"] += 1
        elif c1 is not None and (q1, q2) in ((c1, c2), (c2, c1)):
            counts["flipped"] += 1
        else:
            counts["mismatched"] += 1
    return counts


def _alleles_compatible(query: tuple[str, str], reference: tuple[str, str]) -> bool:
    """True if the query's alleles are the reference's, in either order or on
    the opposite strand. A '0' allele (monomorphic in the upload) matches if
    the other allele does. Swaps/flips still count as compatible here on
    purpose: relabeling them lets check_allele_harmonization see them and
    reject a systematically mis-harmonized file with a clear message,
    instead of those SNPs silently dropping out of the overlap."""
    ref_set = set(reference)
    comp_set = {_complement(a) for a in reference}
    known = {a for a in query if a != "0"}
    if not known:
        return False
    return known <= ref_set or known <= comp_set


def relabel_snp_ids(plink_prefix: str, dummy_bim_path: str) -> dict[str, int]:
    """Rewrites the SNP ID column (2) of <plink_prefix>.bim to the panel's
    'chr<chrom>:<pos>:<ref>:<alt>' IDs, matching on chromosome + position
    (+ compatible alleles, to tell apart variants at the same position).
    infer.sh and check_snp_overlap match on ID alone, so without this an
    upload labeled with rsIDs or without the 'chr' prefix gets ~0 overlap
    even when it covers the panel's positions.

    Only the .bim text is rewritten: .bed genotypes are stored in .bim row
    order, so IDs can change without touching the genotypes. Only ever
    called on the platform's own converted copy, never the user's upload.

    Returns counts: total, already_matching, relabeled, no_position_match,
    allele_mismatch (position in the panel, alleles not compatible),
    duplicate_skipped (would duplicate an ID already present)."""
    by_position: dict[str, list[tuple[str, str, str]]] = {}
    panel_ids: set[str] = set()
    with open(dummy_bim_path) as f:
        for line in f:
            fields = line.split()
            if len(fields) < 6:
                continue
            panel_ids.add(fields[1])
            key = f"{_normalize_chrom(fields[0])}:{fields[3]}"
            by_position.setdefault(key, []).append((fields[1], fields[4].upper(), fields[5].upper()))

    bim_path = plink_prefix + ".bim"
    with open(bim_path) as f:
        rows = [line.rstrip("\n").split("\t") if "\t" in line else line.split() for line in f if line.strip()]

    counts = {
        "total": len(rows),
        "already_matching": 0,
        "relabeled": 0,
        "no_position_match": 0,
        "allele_mismatch": 0,
        "duplicate_skipped": 0,
    }

    # IDs already right are reserved first, so a relabel can never collide
    # with a row that was correct to begin with.
    used_ids = {row[1] for row in rows if len(row) >= 6 and row[1] in panel_ids}

    for row in rows:
        if len(row) < 6:
            continue
        if row[1] in panel_ids:
            counts["already_matching"] += 1
            continue
        candidates = by_position.get(f"{_normalize_chrom(row[0])}:{row[3]}")
        if not candidates:
            counts["no_position_match"] += 1
            continue
        query_alleles = (row[4].upper(), row[5].upper())
        compatible = [c for c in candidates if _alleles_compatible(query_alleles, (c[1], c[2]))]
        if not compatible:
            counts["allele_mismatch"] += 1
            continue
        new_id = compatible[0][0]
        if new_id in used_ids:
            counts["duplicate_skipped"] += 1
            continue
        row[1] = new_id
        used_ids.add(new_id)
        counts["relabeled"] += 1

    tmp_path = bim_path + ".relabel.tmp"
    with open(tmp_path, "w") as f:
        for row in rows:
            f.write("\t".join(row) + "\n")
    os.replace(tmp_path, bim_path)
    return counts


def count_position_overlap(plink_prefix: str, dummy_bim_path: str) -> int:
    """Number of panel positions (chrom:pos) present in the upload, whatever
    its SNP IDs -- reported in the job log next to the ID-based overlap."""
    return len(_read_bim_positions(plink_prefix + ".bim") & _read_bim_positions(dummy_bim_path))


def compute_sample_missing_rates(plink_prefix: str, out_prefix: str) -> dict[str, float]:
    """Per-sample missing rate over the SNPs present in plink_prefix -- called
    on the overlap-extracted set, so the rate is relative to the overlap
    (specifications.docx: "Missing rate calculé par rapport à l'overlap").
    Keyed by IID, which is the sample name infer.sh's predictions use."""
    _run([settings.plink_path, "--bfile", plink_prefix, "--missing", "--out", out_prefix])
    rates: dict[str, float] = {}
    with open(out_prefix + ".imiss") as f:
        next(f)  # header: FID IID MISS_PHENO N_MISS N_GENO F_MISS
        for line in f:
            fields = line.split()
            if len(fields) >= 6:
                rates[fields[1]] = float(fields[5])
    return rates


def run_infer(plink_prefix: str, output_prefix: str) -> tuple[str, str]:
    """Runs Dietnet_inference/infer.sh with the REAL argument order (the
    README's order is wrong -- verified against the script itself):

        bash infer.sh <plink_path> <dietnet_code_path> <dietnet_files_path> <plink_test_prefix> <output_name>

    <output_name> must be a bare relative prefix (not an absolute path):
    infer.sh does `output_dir=${output_name}_DIETNET_RESULTS_BY_MODEL` and
    then writes per-fold results to `${output_dir}/${output_name}_model...`,
    i.e. it concatenates output_name into itself a second time. Passing an
    absolute output_name there produces a broken doubled-absolute path (e.g.
    "/a/b_DIETNET_RESULTS_BY_MODEL//a/b_model5_1_infered.npz"), so every
    fold/rep silently fails to save its .npz and the final combine step has
    nothing to read -- infer.sh doesn't check those exit codes, so it still
    prints "completed" and exits 0. We run with cwd set to output_prefix's
    directory (below) so a relative name still lands in the right place.

    Returns (predictions_file, infer.sh stdout).
    """
    infer_script = os.path.join(settings.dietnet_code_path, "infer.sh")
    output_dir = os.path.dirname(output_prefix)
    output_name = os.path.basename(output_prefix)
    os.makedirs(output_dir, exist_ok=True)
    stdout = _run(
        [
            "bash",
            infer_script,
            settings.plink_path,
            settings.dietnet_code_path,
            settings.dietnet_files_path,
            plink_prefix,
            output_name,
        ],
        cwd=output_dir,
    )
    predictions_file = f"{output_prefix}_dietnet_predictions.txt"
    if not os.path.isfile(predictions_file):
        raise PipelineError("Inference completed without producing a predictions file.")
    return predictions_file, stdout


# --- Results table (specifications.docx, "Tableau prédictions") ---

# 1KGP superpopulation of each of the 24 Diet Network labels. Listed per
# continent in the order of the paper's Fig. 5 axes; this is also the
# column order of the per-population counts in the results table.
POPULATIONS_BY_CONTINENT: dict[str, list[str]] = {
    "AFR": ["YRI", "ESN", "GWD", "LWK", "MSL", "ACB", "ASW"],
    "EUR": ["IBS", "CEUGBR", "TSI", "FIN"],
    "SAS": ["PJL", "BEB", "GIH", "STUITU"],
    "EAS": ["CHB", "CHS", "CDX", "KHV", "JPT"],
    "AMR": ["MXL", "CLM", "PEL", "PUR"],
}
CONTINENT_OF = {pop: continent for continent, pops in POPULATIONS_BY_CONTINENT.items() for pop in pops}
CONTINENT_COLUMNS = ["EUR", "AFR", "SAS", "EAS", "AMR"]  # column order from specifications.docx
POPULATION_COLUMNS = [pop for pops in POPULATIONS_BY_CONTINENT.values() for pop in pops]
RESULTS_TABLE_COLUMNS = (
    ["Sample", "Missing rate (%)", "Continent consensus", "Population consensus"]
    + CONTINENT_COLUMNS
    + POPULATION_COLUMNS
)
N_MODELS = 15


def _consensus(counts: dict[str, int], threshold: int) -> str:
    """The label at least `threshold` of the 15 models agree on, else "NA".
    With threshold > 7 at most one label can qualify."""
    label, votes = max(counts.items(), key=lambda kv: kv[1])
    return label if votes >= threshold else "NA"


def build_results_table(
    predictions_file: str, missing_rates: dict[str, float], consensus_threshold: int
) -> list[dict]:
    """One row per sample from infer.sh's <prefix>_dietnet_predictions.txt
    (columns: samples, model1..model15, all_models): missing rate, continent
    and population consensus, and how many of the 15 models voted for each
    continent and each population. A sample with no missing-rate entry gets
    "NA" there rather than failing the job."""
    rows = []
    with open(predictions_file, newline="") as f:
        for record in csv.DictReader(f, delimiter="\t"):
            votes = [record[f"model{i}"] for i in range(1, N_MODELS + 1)]
            unknown = [v for v in votes if v not in CONTINENT_OF]
            if unknown:
                raise PipelineError("Inference produced an unrecognized population label.")
            pop_counts = {pop: votes.count(pop) for pop in POPULATION_COLUMNS}
            continent_counts = {c: sum(pop_counts[p] for p in POPULATIONS_BY_CONTINENT[c]) for c in CONTINENT_COLUMNS}

            sample = record["samples"]
            rate = missing_rates.get(sample)
            row = {
                "Sample": sample,
                "Missing rate (%)": round(rate * 100, 2) if rate is not None else "NA",
                "Continent consensus": _consensus(continent_counts, consensus_threshold),
                "Population consensus": _consensus(pop_counts, consensus_threshold),
            }
            row.update(continent_counts)
            row.update(pop_counts)
            rows.append(row)
    return rows


def write_results_table(path: str, rows: list[dict]) -> None:
    with open(path, "w") as f:
        f.write("\t".join(RESULTS_TABLE_COLUMNS) + "\n")
        for row in rows:
            f.write("\t".join(str(row[c]) for c in RESULTS_TABLE_COLUMNS) + "\n")


# --- Job log (specifications.docx, "Log file") ---


def write_job_log(path: str, info: dict) -> None:
    """Human-readable summary of one job, shipped in the results zip. `info`
    is assembled by tasks.run_inference_job; keys are documented there."""
    h = info["harmonization"]
    r = info["relabel"]
    rates = [v for v in info["missing_rates"].values()]
    lines = [
        "Diet Network ancestry inference -- job log",
        "=" * 44,
        f"Job ID:                  {info['job_id']}",
        f"Generated (UTC):         {info['generated_at']}",
        f"Input type:              {info['input_type']}",
        f"Samples:                 {info['sample_count']}",
        "",
        "SNPs",
        "----",
        f"In upload after QC (--geno {settings.geno_missingness_threshold}): {r['total']}",
        f"Diet Network panel:      {info['overlap_total']}",
        f"Overlap by position:     {info['overlap_by_position']} (chromosome + position, any SNP ID)",
        f"Overlap by ID:           {info['overlap_count']} (used for inference)",
        f"Overlap by alleles:      {h['matched']} of {h['compared']} compared SNPs have the panel's exact A1/A2",
        f"Minimum for reliability: {settings.min_reliable_snp_overlap}",
        f"Missing-SNP scale factor: {info['overlap_total'] / info['overlap_count']:.6f} (panel SNPs / overlapping SNPs)",
        "",
        "SNP ID relabeling (chromosome + position -> panel ID)",
        "-----------------------------------------------------",
        f"Already matching:        {r['already_matching']}",
        f"Relabeled:               {r['relabeled']}",
        f"Position not in panel:   {r['no_position_match']}",
        f"Allele mismatch at a panel position (not relabeled): {r['allele_mismatch']}",
        f"Would duplicate an ID (not relabeled): {r['duplicate_skipped']}",
        "",
        "Allele harmonization (overlapping SNPs vs panel)",
        "------------------------------------------------",
        f"Compared:   {h['compared']}",
        f"Matched:    {h['matched']}",
        f"Swapped:    {h['swapped']}",
        f"Flipped:    {h['flipped']}",
        f"Ambiguous:  {h['ambiguous']} (A/T or C/G)",
        f"Mismatched: {h['mismatched']}",
        "",
        "Per-sample missing rate (over the overlapping SNPs)",
        "---------------------------------------------------",
    ]
    if rates:
        lines += [
            f"Mean:   {100 * sum(rates) / len(rates):.2f}%",
            f"Max:    {100 * max(rates):.2f}%",
        ]
    else:
        lines.append("Not available")
    lines += [
        "",
        "Predictions",
        "-----------",
        f"Models in ensemble:  {N_MODELS}",
        f"Consensus threshold: {info['consensus_threshold']} of {N_MODELS} models",
        f"Continent consensus reached:  {info['continent_consensus_count']} of {info['sample_count']} samples",
        f"Population consensus reached: {info['population_consensus_count']} of {info['sample_count']} samples",
        f"Reliable (overlap >= {settings.min_reliable_snp_overlap}): {'yes' if info['is_reliable'] else 'NO'}",
        "",
        "infer.sh output",
        "---------------",
        info["infer_stdout"].rstrip(),
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))
