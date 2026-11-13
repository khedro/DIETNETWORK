---
title: Harmonized SNP set (229,986 SNPs)
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# Harmonized SNP set

The fixed list of 229,986 GRCh38 SNPs the models were trained on. It was built so
that 1KGP, CaG GSA and MHIB overlap completely, which allows controlled
comparisons between complete and simulated-incomplete data (Paper p.1463).

## Construction (Paper p.1463)

1. Harmonize CaG GSA and MHIB alleles to GRCh38 (Will Rayner strand tool,
   `GSAMD-24v3-0-EA_20034606_A1-b38` strand file).
2. Drop SNPs whose allele frequency differs by >20% from TOPMed (likely conversion
   errors), SNPs with >10% missingness, and monomorphic sites.
3. Intersect CaG GSA and MHIB → **566,791** SNPs (the "maximal" set).
4. Intersect with 1KGP, then filter with PLINK 1.9: missingness >10% or MAF <5% in
   1KGP removed; LD pruning `--indep-pairwise 50 5 0.5`; HLA region removed
   (chr6:28,510,121–33,480,577).
5. Result: **229,986** SNPs. Missing genotypes imputed with ShapeIT5 in cohort mode,
   with no external reference panel.

Overlap in other cohorts: AoU 204,667; CaG Omni 170,538; CaG Axiom 55,250 (Paper p.1463).

## In the code

- `DN_SNPS/dietnet_snps.txt` — the SNP IDs; `infer.sh` extracts these from a query
  ([infer.sh:20-25](../../Dietnet_inference/infer.sh#L20-L25)).
- `DN_SNPS/dummy.{bed,bim,fam}` — one 1KGP sample carrying all SNPs with the panel's
  canonical A1/A2; used to fill missing SNPs and, in the platform, to check allele
  harmonization ([pipeline.py:251-289](../../worker/worker/pipeline.py#L251-L289)).
- **SNP ID format** is `chr<chrom>:<pos>:<ref>:<alt>` (e.g. `chr1:12345:A:G`). Queries
  using rsIDs or no `chr` prefix get near-zero overlap; the worker detects this by
  comparing chrom:pos instead ([pipeline.py:198-227](../../worker/worker/pipeline.py#L198-L227)).
- Everything uses `--real-ref-alleles`, so the query's allele order is trusted as
  given. A swapped or strand-flipped file would silently invert dosages. This is why
  the platform's harmonization pre-check exists.

## See also
- [Missing-SNP handling](missing-snp-handling.md)
- [Datasets](../entities/datasets.md)
- [Worker pipeline](../code/worker-pipeline.md)
