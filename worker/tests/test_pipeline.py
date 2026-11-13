"""Unit tests for the pure-Python pre-flight checks in worker/worker/pipeline.py.

count_samples and check_allele_harmonization take no external dependencies
and run anywhere. check_snp_overlap shells out to plink against the
DN_SNPS panel baked into the worker image, so it's skipped unless both are
available (run this file inside a worker container -- see
tests/run_unit_tests.sh, which mounts dataTest/fixtures in and sets
FIXTURES_DIR).
"""
import os

import pytest

import conftest
from worker.config import settings
from worker.pipeline import (
    CONTINENT_COLUMNS,
    POPULATION_COLUMNS,
    RESULTS_TABLE_COLUMNS,
    OPTIONAL_INFER_OUTPUTS,
    REQUIRED_INFER_OUTPUTS,
    PipelineError,
    QualityControlError,
    build_results_table,
    check_allele_harmonization,
    check_snp_overlap,
    compute_sample_missing_rates,
    count_position_overlap,
    count_samples,
    detect_id_labeling_mismatch,
    relabel_snp_ids,
    run_infer,
    write_job_log,
    write_results_table,
)

PLINK_AVAILABLE = os.path.isfile(settings.plink_path)
PANEL_AVAILABLE = os.path.isdir(os.path.join(settings.dietnet_files_path, "DN_SNPS"))
FIXTURES_AVAILABLE = bool(conftest.FIXTURES_DIR) and os.path.isdir(conftest.FIXTURES_DIR)

requires_container = pytest.mark.skipif(
    not (PLINK_AVAILABLE and PANEL_AVAILABLE and FIXTURES_AVAILABLE),
    reason="needs plink + DN_SNPS panel (baked into the worker image) and dataTest/fixtures mounted in "
    "-- run via tests/run_unit_tests.sh, not bare pytest on the host",
)


requires_plink = pytest.mark.skipif(not PLINK_AVAILABLE, reason="needs the plink binary from the worker image")


# --- count_samples -- pure, no dependencies ---


def test_count_samples(tmp_path):
    fam = tmp_path / "x.fam"
    fam.write_text("fam1 ind1 0 0 1 -9\nfam1 ind2 0 0 2 -9\nfam2 ind3 0 0 1 -9\n")
    assert count_samples(str(tmp_path / "x")) == 3


def test_count_samples_empty(tmp_path):
    (tmp_path / "x.fam").write_text("")
    assert count_samples(str(tmp_path / "x")) == 0


# --- check_allele_harmonization -- pure, no dependencies ---


def _write_bim(path, rows):
    """rows: list of (snp_id, a1, a2)."""
    with open(path, "w") as f:
        for i, (snp_id, a1, a2) in enumerate(rows, start=1):
            f.write(f"1\t{snp_id}\t0\t{i}\t{a1}\t{a2}\n")


def test_check_allele_harmonization_classifies_each_case(tmp_path):
    # Reference (panel) alleles, one SNP per classification:
    reference = [
        ("matched", "A", "G"),  # non-palindromic
        ("swapped", "A", "G"),  # non-palindromic order swap
        ("flipped", "A", "G"),  # strand complement, same order
        ("ambiguous", "A", "T"),  # palindromic pair -- swap and flip look identical
        ("mismatched", "A", "G"),  # genuinely different alleles
        ("missing_code", "0", "G"),  # '0' -- excluded from comparison entirely
        ("only_in_reference", "C", "T"),  # not present in query at all
    ]
    query = [
        ("matched", "A", "G"),  # == reference
        ("swapped", "G", "A"),  # order reversed
        ("flipped", "T", "C"),  # complement of A/G, same order
        ("ambiguous", "T", "A"),  # order reversed on a palindromic pair
        ("mismatched", "C", "G"),  # neither swap nor flip of A/G
        ("missing_code", "0", "G"),
        ("only_in_query", "A", "C"),  # not present in reference -- ignored
    ]
    ref_path, query_path = tmp_path / "ref.bim", tmp_path / "query.bim"
    _write_bim(ref_path, reference)
    _write_bim(query_path, query)

    counts = check_allele_harmonization(str(query_path), str(ref_path))

    assert counts == {
        "compared": 5,  # excludes the two '0'-coded and the two SNPs only on one side
        "matched": 1,
        "swapped": 1,
        "flipped": 1,
        "ambiguous": 1,
        "mismatched": 1,
    }


def test_check_allele_harmonization_all_matched_below_threshold(tmp_path):
    rows = [(f"snp{i}", "A", "G") for i in range(20)]
    ref_path, query_path = tmp_path / "ref.bim", tmp_path / "query.bim"
    _write_bim(ref_path, rows)
    _write_bim(query_path, rows)

    counts = check_allele_harmonization(str(query_path), str(ref_path))
    mismatched = counts["swapped"] + counts["flipped"] + counts["ambiguous"]
    assert counts["compared"] == 20
    assert mismatched == 0


# --- check_snp_overlap -- shells out to plink; needs the real panel ---


@requires_container
def test_check_snp_overlap_low_overlap_fixture_below_threshold(tmp_path):
    overlap_count, overlap_total = check_snp_overlap(
        os.path.join(conftest.FIXTURES_DIR, "low_overlap"), str(tmp_path / "out")
    )
    assert overlap_total == 229986  # full DN_SNPS panel size
    assert overlap_count <= 400  # fixture only has 400 SNPs to begin with
    assert overlap_count < settings.min_reliable_snp_overlap


@requires_container
def test_check_snp_overlap_positive_control_above_threshold(tmp_path):
    positive_control = os.path.join(
        conftest.FIXTURES_DIR,
        "..",
        "1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed",
    )
    overlap_count, overlap_total = check_snp_overlap(positive_control, str(tmp_path / "out"))
    assert overlap_count >= settings.min_reliable_snp_overlap


# --- detect_id_labeling_mismatch -- needs the real panel + dummy.bim, no plink call ---


def _real_panel_rows(n=2000):
    """First n rows of dummy.bim -- real chrom/pos/alleles from the actual
    reference panel, used below as a base to swap in different ID
    conventions while keeping genuinely-matching positions."""
    dummy_bim_path = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dummy.bim")
    with open(dummy_bim_path) as f:
        return [line.split() for line in f][:n]


@requires_container
def test_detect_id_labeling_mismatch_true_for_rsid_style_ids(tmp_path):
    # Same chrom+pos+alleles as the real panel, but rsID-style IDs instead
    # of the panel's "chr1:pos:ref:alt" convention -- check_snp_overlap's
    # ID-based --extract would find ~0 overlap here even though the
    # underlying positions are identical. This is what the old
    # chr-prefix-only version of this check could NOT catch.
    bim_path = tmp_path / "query.bim"
    with open(bim_path, "w") as f:
        for i, (chrom, _snp_id, cm, pos, a1, a2) in enumerate(_real_panel_rows(), start=1):
            f.write(f"{chrom}\trs{1000000 + i}\t{cm}\t{pos}\t{a1}\t{a2}\n")

    assert detect_id_labeling_mismatch(str(tmp_path / "query")) is True


@requires_container
def test_detect_id_labeling_mismatch_true_when_ids_missing_chr(tmp_path):
    bim_path = tmp_path / "query.bim"
    with open(bim_path, "w") as f:
        for chrom, snp_id, cm, pos, a1, a2 in _real_panel_rows():
            stripped = snp_id[3:] if snp_id.startswith("chr") else snp_id  # "chr1:123:A:G" -> "1:123:A:G"
            f.write(f"{chrom}\t{stripped}\t{cm}\t{pos}\t{a1}\t{a2}\n")

    assert detect_id_labeling_mismatch(str(tmp_path / "query")) is True


@requires_container
def test_detect_id_labeling_mismatch_false_for_genuinely_low_overlap(tmp_path):
    # low_overlap fixture's IDs and positions already match the panel's own
    # convention -- its low overlap is real, not a labeling artifact.
    assert detect_id_labeling_mismatch(os.path.join(conftest.FIXTURES_DIR, "low_overlap")) is False


@requires_container
def test_detect_id_labeling_mismatch_false_when_already_matching(tmp_path):
    positive_control = os.path.join(
        conftest.FIXTURES_DIR,
        "..",
        "1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed",
    )
    assert detect_id_labeling_mismatch(positive_control) is False



# --- relabel_snp_ids -- pure, reference .bim written by the test ---


def _write_bim_rows(path, rows):
    """rows: list of (chrom, snp_id, pos, a1, a2)."""
    with open(path, "w") as f:
        for chrom, snp_id, pos, a1, a2 in rows:
            f.write(f"{chrom}\t{snp_id}\t0\t{pos}\t{a1}\t{a2}\n")


PANEL_ROWS = [
    ("1", "chr1:100:A:G", 100, "A", "G"),
    ("1", "chr1:200:C:T", 200, "C", "T"),
    ("1", "chr1:300:A:C", 300, "A", "C"),  # two panel variants at one position
    ("1", "chr1:300:A:T", 300, "A", "T"),
    ("2", "chr2:400:G:T", 400, "G", "T"),
    ("2", "chr2:500:A:G", 500, "A", "G"),
    ("2", "chr2:700:A:G", 700, "A", "G"),
]


def test_relabel_snp_ids_rewrites_by_position_and_alleles(tmp_path):
    panel = tmp_path / "dummy.bim"
    _write_bim_rows(panel, PANEL_ROWS)
    query = [
        ("1", "chr1:100:A:G", 100, "A", "G"),  # already the panel ID
        ("1", "rs200", 200, "T", "C"),  # swapped alleles -> still relabeled (harmonization check judges it)
        ("1", "rs300", 300, "T", "A"),  # picks the A/T variant, not A/C
        ("2", "rs400", 400, "C", "A"),  # strand flip of G/T -> relabeled
        ("2", "rs500", 500, "C", "G"),  # not A/G in any order or strand -> left alone
        ("3", "rs600", 600, "A", "G"),  # position not in panel
        ("chr1", "dup100", 100, "A", "G"),  # 'chr1' chrom normalized; ID already taken -> skipped
        ("2", "rsmono", 700, "0", "G"),  # monomorphic in upload, known allele matches
    ]
    _write_bim_rows(tmp_path / "query.bim", query)

    counts = relabel_snp_ids(str(tmp_path / "query"), str(panel))

    assert counts == {
        "total": 8,
        "already_matching": 1,
        "relabeled": 4,
        "no_position_match": 1,
        "allele_mismatch": 1,
        "duplicate_skipped": 1,
        "filled_missing_allele": 1,
    }
    ids = [line.split("\t")[1] for line in (tmp_path / "query.bim").read_text().splitlines()]
    assert ids == [
        "chr1:100:A:G",
        "chr1:200:C:T",
        "chr1:300:A:T",
        "chr2:400:G:T",
        "rs500",
        "rs600",
        "dup100",
        "chr2:700:A:G",
    ]
    # Everything except the ID column is untouched (row order == .bed order),
    # apart from the monomorphic row's '0' allele, filled from the panel.
    expected = [list(r) for r in query]
    expected[7][3] = "A"
    for original, line in zip(expected, (tmp_path / "query.bim").read_text().splitlines()):
        fields = line.split("\t")
        assert (fields[0], fields[3], fields[4], fields[5]) == (original[0], str(original[2]), original[3], original[4])


def test_relabel_snp_ids_fills_monomorphic_allele_only_in_panel_order(tmp_path):
    """infer.sh rebuilds IDs as chr:pos:A2:A1 from the .bim, so a '0' allele
    must become the panel's -- but only where that yields the panel's order."""
    panel = tmp_path / "dummy.bim"
    _write_bim_rows(panel, PANEL_ROWS)
    _write_bim_rows(
        tmp_path / "query.bim",
        [
            ("1", "chr1:100:A:G", 100, "0", "G"),  # A2 is the panel's A2 -> A1 filled
            ("1", "chr1:200:C:T", 200, "C", "0"),  # A1 is the panel's A1 -> A2 filled
            ("2", "chr2:500:A:G", 500, "0", "A"),  # observed allele in the wrong column -> left alone
        ],
    )

    counts = relabel_snp_ids(str(tmp_path / "query"), str(panel))

    assert counts["filled_missing_allele"] == 2
    rows = [line.split("\t") for line in (tmp_path / "query.bim").read_text().splitlines()]
    assert [(r[4], r[5]) for r in rows] == [("A", "G"), ("C", "T"), ("0", "A")]


def test_relabel_snp_ids_is_idempotent(tmp_path):
    panel = tmp_path / "dummy.bim"
    _write_bim_rows(panel, PANEL_ROWS)
    _write_bim_rows(tmp_path / "query.bim", [("1", "rs1", 100, "A", "G"), ("1", "rs2", 200, "C", "T")])

    first = relabel_snp_ids(str(tmp_path / "query"), str(panel))
    second = relabel_snp_ids(str(tmp_path / "query"), str(panel))

    assert first["relabeled"] == 2
    assert second["relabeled"] == 0 and second["already_matching"] == 2


def test_relabel_snp_ids_handles_space_delimited_bim(tmp_path):
    panel = tmp_path / "dummy.bim"
    _write_bim_rows(panel, PANEL_ROWS)
    (tmp_path / "query.bim").write_text("1 rs1 0 100 A G\n")

    assert relabel_snp_ids(str(tmp_path / "query"), str(panel))["relabeled"] == 1
    assert (tmp_path / "query.bim").read_text() == "1\tchr1:100:A:G\t0\t100\tA\tG\n"


def test_count_position_overlap_ignores_ids(tmp_path):
    panel = tmp_path / "dummy.bim"
    _write_bim_rows(panel, PANEL_ROWS)
    _write_bim_rows(tmp_path / "query.bim", [("chr1", "x", 100, "A", "G"), ("1", "y", 300, "A", "C"), ("9", "z", 1, "A", "G")])

    assert count_position_overlap(str(tmp_path / "query"), str(panel)) == 2


# --- build_results_table / write_results_table -- pure ---


def _write_predictions(path, samples):
    """samples: list of (sample_id, [15 labels]), in the layout of infer.sh's
    <prefix>_predictions_bymodel_population.txt."""
    header = ["Samples", "F_MISS"] + [f"model{i}" for i in range(1, 16)]
    with open(path, "w") as f:
        f.write("\t".join(header) + "\n")
        for sample, votes in samples:
            assert len(votes) == 15
            f.write("\t".join([sample, "0.5"] + votes) + "\n")


def test_build_results_table_consensus_and_counts(tmp_path):
    preds = tmp_path / "preds.txt"
    _write_predictions(
        preds,
        [
            ("s1", ["GWD"] * 13 + ["YRI", "TSI"]),  # pop 13 >= 12; AFR 14
            ("s2", ["YRI"] * 12 + ["IBS"] * 3),  # exactly at the threshold
            ("s3", ["YRI"] * 11 + ["GWD"] * 4),  # AFR 15 but no population reaches 12
            ("s4", ["CHB"] * 7 + ["MXL"] * 8),  # no continent reaches 12
        ],
    )
    rows = build_results_table(str(preds), {"s1": 0.1, "s2": 0.05, "s3": 0.0123}, consensus_threshold=12)

    by_sample = {r["Sample"]: r for r in rows}
    assert [r["Sample"] for r in rows] == ["s1", "s2", "s3", "s4"]
    assert (by_sample["s1"]["Continent consensus"], by_sample["s1"]["Population consensus"]) == ("AFR", "GWD")
    assert (by_sample["s2"]["Continent consensus"], by_sample["s2"]["Population consensus"]) == ("AFR", "YRI")
    assert (by_sample["s3"]["Continent consensus"], by_sample["s3"]["Population consensus"]) == ("AFR", "NA")
    assert (by_sample["s4"]["Continent consensus"], by_sample["s4"]["Population consensus"]) == ("NA", "NA")

    assert by_sample["s1"]["Missing rate (%)"] == 10.0
    assert by_sample["s3"]["Missing rate (%)"] == 1.23
    assert by_sample["s4"]["Missing rate (%)"] == "NA"  # no missing-rate entry for this sample

    s1 = by_sample["s1"]
    assert (s1["AFR"], s1["EUR"], s1["SAS"], s1["EAS"], s1["AMR"]) == (14, 1, 0, 0, 0)
    assert (s1["GWD"], s1["YRI"], s1["TSI"]) == (13, 1, 1)
    for row in rows:
        assert sum(row[c] for c in CONTINENT_COLUMNS) == 15
        assert sum(row[p] for p in POPULATION_COLUMNS) == 15


def test_build_results_table_threshold_is_configurable(tmp_path):
    preds = tmp_path / "preds.txt"
    _write_predictions(preds, [("s1", ["YRI"] * 11 + ["GWD"] * 4)])

    assert build_results_table(str(preds), {}, consensus_threshold=11)[0]["Population consensus"] == "YRI"
    assert build_results_table(str(preds), {}, consensus_threshold=12)[0]["Population consensus"] == "NA"


def test_build_results_table_rejects_unknown_label(tmp_path):
    preds = tmp_path / "preds.txt"
    _write_predictions(preds, [("s1", ["YRI"] * 14 + ["XXX"])])
    with pytest.raises(PipelineError):
        build_results_table(str(preds), {}, consensus_threshold=12)


def test_population_columns_match_model_labels():
    """The table's 24 population columns must be exactly the labels
    Dietnet_inference/population_config.py lists as model outputs."""
    import re

    script = os.path.join(settings.dietnet_code_path, "population_config.py")
    if not os.path.isfile(script):  # host run: fall back to the repo copy
        script = os.path.join(os.path.dirname(__file__), "..", "..", "Dietnet_inference", "population_config.py")
    if not os.path.isfile(script):
        pytest.skip("population_config.py not available")
    block = re.search(r"dn_label_order = \[(.*?)\]", open(script).read(), re.S).group(1)
    model_labels = set(re.findall(r"'([A-Z]+)'", block))

    assert len(model_labels) == 24
    assert set(POPULATION_COLUMNS) == model_labels
    assert len(POPULATION_COLUMNS) == 24


def test_write_results_table_header_and_order(tmp_path):
    preds = tmp_path / "preds.txt"
    _write_predictions(preds, [("s1", ["PUR"] * 15)])
    rows = build_results_table(str(preds), {"s1": 0.0}, consensus_threshold=12)
    out = tmp_path / "table.tsv"
    write_results_table(str(out), rows)

    lines = out.read_text().splitlines()
    assert lines[0].split("\t") == RESULTS_TABLE_COLUMNS
    assert lines[0].split("\t")[:9] == [
        "Sample", "Missing rate (%)", "Continent consensus", "Population consensus", "EUR", "AFR", "SAS", "EAS", "AMR",
    ]
    values = dict(zip(RESULTS_TABLE_COLUMNS, lines[1].split("\t")))
    assert values["Continent consensus"] == "AMR" and values["Population consensus"] == "PUR"
    assert values["AMR"] == "15" and values["PUR"] == "15" and values["YRI"] == "0"


# --- write_job_log -- pure ---


def test_write_job_log_contains_spec_fields(tmp_path):
    info = {
        "job_id": "job-123",
        "generated_at": "2026-10-01 12:00:00",
        "input_type": "plink",
        "sample_count": 3,
        "relabel": {"total": 1000, "already_matching": 10, "relabeled": 900, "no_position_match": 80,
                    "allele_mismatch": 7, "duplicate_skipped": 3},
        "overlap_by_position": 917,
        "overlap_count": 910,
        "overlap_total": 229986,
        "harmonization": {"compared": 910, "matched": 905, "swapped": 2, "flipped": 1, "ambiguous": 1, "mismatched": 1},
        "missing_rates": {"a": 0.0, "b": 0.1, "c": 0.2},
        "consensus_threshold": 12,
        "continent_consensus_count": 3,
        "population_consensus_count": 2,
        "is_reliable": False,
        "qc_population_accuracy": 0.9694,
        "qc_continent_accuracy": 0.99798,
        "missing_optional_outputs": ["result_representation_pop.png"],
        "infer_stdout": "The SNP overlap with Diet Network is: 910 out of 229986\n",
    }
    path = tmp_path / "log.txt"
    write_job_log(str(path), info)
    text = path.read_text()

    for expected in [
        "Job ID:                  job-123",
        "Overlap by position:     917",
        "Overlap by ID:           910",
        "Overlap by alleles:      905 of 910",
        "Relabeled:               900",
        "Mean:   10.00%",
        "Max:    20.00%",
        "Consensus threshold: 12 of 15 models",
        "Population consensus reached: 2 of 3 samples",
        "Reliable (overlap >= 1000): NO",
        "The SNP overlap with Diet Network is: 910 out of 229986",
        "Mean continent-level accuracy:  99.80% (minimum 95%)",
        "Mean population-level accuracy: 96.94%",
        "Not produced (see infer.sh output): result_representation_pop.png",
    ]:
        assert expected in text, expected


# --- compute_sample_missing_rates -- runs plink on a tiny hand-built .bed ---


def _write_plink_set(prefix, genotypes):
    """genotypes[snp][sample]: 0/1/2 copies of A2, or None for missing.
    Writes a SNP-major PLINK1 .bed: 2 bits per sample, first sample in the
    lowest bits; 00 = hom A1, 01 = missing, 10 = het, 11 = hom A2."""
    codes = {0: 0b00, None: 0b01, 1: 0b10, 2: 0b11}
    n_samples = len(genotypes[0])
    with open(str(prefix) + ".bed", "wb") as f:
        f.write(b"\x6c\x1b\x01")
        for snp in genotypes:
            for start in range(0, n_samples, 4):
                byte = 0
                for offset, g in enumerate(snp[start : start + 4]):
                    byte |= codes[g] << (2 * offset)
                f.write(bytes([byte]))
    with open(str(prefix) + ".bim", "w") as f:
        for i in range(len(genotypes)):
            f.write(f"1\tchr1:{1000 + i}:A:G\t0\t{1000 + i}\tG\tA\n")
    with open(str(prefix) + ".fam", "w") as f:
        for j in range(n_samples):
            f.write(f"fam{j}\tind{j}\t0\t0\t0\t-9\n")


@requires_plink
def test_compute_sample_missing_rates_exact_values(tmp_path):
    # 4 SNPs x 5 samples; ind0..ind4 miss 0, 1, 2, 3 and 0 of the 4 SNPs.
    genotypes = [
        [0, None, None, None, 2],
        [1, 1, None, None, 1],
        [2, 2, 2, None, 0],
        [0, 0, 1, 2, 1],
    ]
    _write_plink_set(tmp_path / "tiny", genotypes)

    rates = compute_sample_missing_rates(str(tmp_path / "tiny"), str(tmp_path / "miss"))

    assert rates == {"ind0": 0.0, "ind1": 0.25, "ind2": 0.5, "ind3": 0.75, "ind4": 0.0}


@requires_container
def test_compute_sample_missing_rates_positive_control(tmp_path):
    positive_control = os.path.join(
        conftest.FIXTURES_DIR,
        "..",
        "1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed",
    )
    rates = compute_sample_missing_rates(positive_control, str(tmp_path / "miss"))
    assert len(rates) == 2504
    assert all(0.0 <= r <= 1.0 for r in rates.values())


# --- relabel_snp_ids against the real panel ---


@requires_container
def test_relabel_snp_ids_restores_full_overlap_for_rsid_fixture(tmp_path):
    """rsid_labels fixture = positive control with every ID replaced by an
    rsID. After relabeling by position, every SNP should be back on its
    panel ID."""
    import shutil

    src = os.path.join(conftest.FIXTURES_DIR, "rsid_labels")
    shutil.copy(src + ".bim", tmp_path / "q.bim")
    dummy_bim_path = os.path.join(settings.dietnet_files_path, "DN_SNPS", "dummy.bim")

    counts = relabel_snp_ids(str(tmp_path / "q"), dummy_bim_path)

    assert counts["total"] == 229986
    assert counts["relabeled"] == 229986
    assert counts["already_matching"] == 0


# --- run_infer -- a fake infer.sh stands in for Dietnet_inference/infer.sh ---

FAKE_QC_OK = """Population-level accuracy by model:
Average population-level accuracy across all models: 0.9694242712040742
Average continent-level accuracy across all models: 0.9979840662814166
"""
FAKE_QC_FAIL = """Average continent-level accuracy across all models: 0.9411681766467678
Stopping pipeline: Mean continent-level accuracy is below 95% (94.12%)
Exit.
"""


def _fake_infer(tmp_path, monkeypatch, body):
    """Points settings.dietnet_code_path at a directory whose infer.sh runs
    `body` (with $5 = output name, cwd = results dir) and records its args."""
    code = tmp_path / "code"
    code.mkdir()
    (code / "infer.sh").write_text('echo "$@" > args.txt\n' + body)
    monkeypatch.setattr(settings, "dietnet_code_path", str(code))
    results = tmp_path / "results"
    results.mkdir()
    return str(results / "result")


def _touch_outputs(suffixes):
    return "".join(f'touch "$5{s}"\n' for s in suffixes)


def test_run_infer_passes_folds_and_reps_and_returns_outputs(tmp_path, monkeypatch):
    prefix = _fake_infer(
        tmp_path,
        monkeypatch,
        f"cat <<'EOF'\n{FAKE_QC_OK}EOF\n"
        + _touch_outputs(REQUIRED_INFER_OUTPUTS + OPTIONAL_INFER_OUTPUTS)
        + "mkdir -p 1KGP_RESULTS && touch 1KGP_RESULTS/x.npz $5.hdf5\n",
    )

    result = run_infer("/converted/query", prefix)

    args = open(os.path.join(os.path.dirname(prefix), "args.txt")).read().split()
    assert args[3:] == ["/converted/query", "result", "5", "3"]
    assert result.by_model_file == prefix + "_predictions_bymodel_population.txt"
    assert result.qc_continent_accuracy == pytest.approx(0.99798, abs=1e-5)
    assert result.qc_population_accuracy == pytest.approx(0.96942, abs=1e-5)
    assert result.missing_optional_outputs == []
    # scratch left by infer.sh is removed; real outputs are kept
    assert not os.path.exists(os.path.join(os.path.dirname(prefix), "1KGP_RESULTS"))
    assert not os.path.exists(prefix + ".hdf5")
    assert os.path.isfile(prefix + "_predictions.txt")


def test_run_infer_qc_stop_is_a_user_facing_error_and_cleans_up(tmp_path, monkeypatch):
    prefix = _fake_infer(
        tmp_path,
        monkeypatch,
        f"cat <<'EOF'\n{FAKE_QC_FAIL}EOF\n"
        + 'touch "$5_included_snps.txt"; mkdir -p 1KGP_RESULTS; touch 1KGP_RESULTS/big.npz\nexit 1\n',
    )

    with pytest.raises(QualityControlError) as exc:
        run_infer("/converted/query", prefix)

    assert "94.12% continent-level accuracy" in str(exc.value)
    assert "below the 95% required" in str(exc.value)
    assert not os.path.exists(os.path.join(os.path.dirname(prefix), "1KGP_RESULTS"))


def test_run_infer_other_failure_is_generic(tmp_path, monkeypatch):
    prefix = _fake_infer(tmp_path, monkeypatch, "echo boom; exit 3\n")
    with pytest.raises(PipelineError) as exc:
        run_infer("/converted/query", prefix)
    assert not isinstance(exc.value, QualityControlError)


def test_run_infer_exit_0_without_predictions_fails(tmp_path, monkeypatch):
    """infer.sh doesn't check its python steps' exit codes."""
    prefix = _fake_infer(tmp_path, monkeypatch, f"cat <<'EOF'\n{FAKE_QC_OK}EOF\n" + _touch_outputs(OPTIONAL_INFER_OUTPUTS))
    with pytest.raises(PipelineError, match="without producing a predictions file"):
        run_infer("/converted/query", prefix)


def test_run_infer_missing_plots_are_reported_not_fatal(tmp_path, monkeypatch):
    prefix = _fake_infer(
        tmp_path,
        monkeypatch,
        f"cat <<'EOF'\n{FAKE_QC_OK}EOF\n" + _touch_outputs(REQUIRED_INFER_OUTPUTS + OPTIONAL_INFER_OUTPUTS[:3]),
    )
    result = run_infer("/converted/query", prefix)
    assert result.missing_optional_outputs == ["result_representation_pop.png", "result_representation_continent.png"]
