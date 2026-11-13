---
title: Datasets
type: entity
sources: [paper]
updated: 2026-09-28
---

# Datasets

One training reference (1KGP) and three evaluation biobanks. Only the 1KGP-trained
models and files are distributed (Zenodo). The biobank data is access-controlled.

## 1KGP
1000 Genomes Project, 30× whole-genome sequencing on GRCh38 (IGSR). 2,504 samples,
26 populations, 5 continents (Paper p.1463).
- CEU+GBR merged → **CEUGBR**, ITU+STU merged → **STUITU** (low F_ST, Notes S1.1),
  giving **24** populations.
- Merged groups downsampled to the largest population in their continent
  (n_CEUGBR = 107, n_STUITU = 105) → **2,322** training individuals.
- Split per model: 60% train / 20% valid / 20% test, population-balanced.

## CARTaGENE (CaG)
Quebec population biobank (Paper p.1462–1463). Three array subsets:

| Subset | Array | N | SNPs overlapping the training set |
|---|---|---|---|
| GSA | Illumina GSA v2 + MD panel + CaG add-on | 17,286 | 229,986 (complete) |
| Omni | Illumina HumanOmni2.5-8v1 | 937 | 170,538 |
| Axiom | Affymetrix Axiom UK Biobank | 990 | 55,250 |

Labels from self-report plus **all four grandparents** born in the country:
French Canadian 9,437 (GSA), 772 (Axiom), 643 (Omni); Italian 367; Chinese 107;
Haitian 230; Moroccan 160 (GSA only).

## Montreal Heart Institute Biobank (MHIB)
16,707 individuals, GSA v3.0-MD array. Labels from self-reported ethnicity, refined
genetically: 105 North Africans found by PCA among self-reported White; individuals
whose RFMix v2 ancestry contradicted self-report were removed (Paper p.1463).
Groups: French Canadian 12,884; Italian 419; African 117; Asian 62; North African 105.
Complete overlap with the training SNPs.

## All of Us (AoU)
447,278 individuals, Illumina Global Diversity Array, Controlled Tier v8, analyzed
on the Researcher Workbench. 204,667 SNPs overlap (~11% missing). Self-reported
groups: White 231,168; Black or African American 74,511; Asian 12,640; Hispanic or
Latino 69,284. Results are reported only for profiles with ≥ 20 individuals
(Paper p.1463).

## Results by dataset (short)
- Italians → TSI; Chinese → East Asian; Haitians and Africans → ACB/YRI (admixed
  ancestry not in the training set is still captured); French Canadians → CEUGBR/IBS
  (Paper p.1467, Fig. 1C–D).
- AoU Hispanic/Latino → PUR, MXL, CLM, PEL (Fig. 2A).
- Moroccans / North Africans → spread over PUR, TSI, IBS; they form a distinct
  profile in latent space (Fig. 3).

## See also
- [Populations](populations.md)
- [Harmonized SNP set](../concepts/harmonized-snp-set.md)
- [Latent representations](../concepts/latent-representations.md)
