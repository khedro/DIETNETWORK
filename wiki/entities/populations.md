---
title: The 24 output populations
type: entity
sources: [paper, code]
updated: 2026-09-28
---

# The 24 output populations

The model's output classes: the 26 1KGP populations with CEU+GBR and ITU+STU merged
(Paper p.1463). Listed in the class-index order used by
[inference_combine_results.py:9-13](../../Dietnet_inference/inference_combine_results.py#L9-L13).

| # | Code | Superpopulation | Notes from the paper |
|---|---|---|---|
| 0 | ACB | African (admixed) | Predicted for Haitians/Africans. Assigned by eliminating alternatives |
| 1 | ASW | African (admixed) | Only population where PCA+RF beats Diet Network; often called ACB |
| 2 | BEB | South Asian | |
| 3 | CDX | East Asian | PCA+RF and Rye confuse it with KHV |
| 4 | CEUGBR | European | Merged CEU+GBR. Main French Canadian prediction |
| 5 | CHB | East Asian | |
| 6 | CHS | East Asian | |
| 7 | CLM | American (admixed) | Assigned by eliminating alternatives |
| 8 | ESN | African | PCA+RF and Rye confuse it with YRI |
| 9 | FIN | European | |
| 10 | GIH | South Asian | |
| 11 | GWD | African | |
| 12 | IBS | European | Second French Canadian prediction |
| 13 | JPT | East Asian | |
| 14 | KHV | East Asian | |
| 15 | LWK | African | |
| 16 | MSL | African | |
| 17 | MXL | American (admixed) | Positive within-group attribution |
| 18 | PEL | American (admixed) | Positive within-group attribution |
| 19 | PJL | South Asian | |
| 20 | PUR | American (admixed) | **Default class** under ambiguity or heavy missingness |
| 21 | STUITU | South Asian | Merged STU+ITU |
| 22 | TSI | European | Predicted for Italians |
| 23 | YRI | African | |

Superpopulations follow standard 1KGP groupings (Paper Table S1). Missing from the
reference entirely: North Africa and West Asia (Paper p.1473).

## See also
- [Datasets](datasets.md)
- [F_ST](../concepts/fst.md)
- [15-model ensemble](../concepts/ensemble.md)
