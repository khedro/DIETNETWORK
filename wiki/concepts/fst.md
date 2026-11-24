---
title: F_ST and what the model learned
type: concept
sources: [paper]
updated: 2026-09-28
---

# F_ST vs attributions

F_ST measures allele-frequency differentiation between populations: near 0 within a
continent, higher between continents. The paper uses pairwise F_ST, computed with
VCFtools 0.1.16 over all 229,986 SNPs for every pair of the 24 populations, as a
biological benchmark for the [attributions](feature-attribution.md) (Paper p.1465, 1470–1471).

## Findings

1. **Important SNPs are differentiated SNPs.** The 10 SNPs with the highest global
   attribution all rank in the top 7% by F_ST; 15 random SNPs show much lower F_ST
   (Fig. 5B).
2. **Same block structure.** The population × population attribution matrix has the
   same continental blocks as the F_ST matrix (Fig. 5A vs 5C).
3. **Per-SNP mirroring.** For top SNPs, pairwise attribution patterns follow their
   F_ST profiles. Low-F_ST (shared) SNPs act as positive evidence for similar targets;
   high-F_ST SNPs act as negative evidence (Fig. 5D).

## Two prediction strategies

- **Most populations: accumulating evidence for.** Strong positive diagonal in the
  attribution matrix.
- **Admixed ACB, ASW, CLM, PUR: eliminating alternatives.** Near-zero or negative
  diagonal and negative scores across other columns. High individual variation in
  ancestry proportions leaves no shared population-specific signal (Paper p.1471, 1473).
  PEL and MXL, also admixed, still show positive within-group signal.
- **PUR as default.** PUR's correct-classification attribution is the closest to 0.
  The model assigns PUR when nothing else fits, which explains PUR predictions under
  99% missingness and for near-mean baselines (Paper p.1473).

## Side finding: data quality

Earlier Diet Network models trained on the 1KGP *genotyping* dataset (3,450 samples)
had high-attribution SNPs with unexpected divergence patterns (Fig. S13), and that
dataset contained related individuals. This motivated switching to the 30×
sequencing dataset (Paper p.1473).

## See also
- [Populations](../entities/populations.md)
- [Feature attribution](feature-attribution.md)
