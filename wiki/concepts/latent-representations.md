---
title: Latent representations (last hidden layer)
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# Latent representations

The last hidden layer (100 units) of each model is a compressed description of an
individual. Concatenating it across the 15 models gives a 1,500-d vector. A PCA of
these vectors shows where a query individual sits relative to the training
populations, including people from populations the model was never trained on
(Paper p.1464, 1468–1469, Fig. 3B).

## Method (Paper p.1464)

1. Extract last-hidden-layer activations for all 1KGP individuals from all 15 models → 1,500-d.
2. Fit PCA (scikit-learn 1.0.1) on 1KGP.
3. Project out-of-distribution individuals (CaG Moroccans, MHIB North Africans) onto it.

## Findings

- 1KGP populations form continental clusters in PC1/PC2 (Fig. 3B).
- North Africans are **not** absorbed into any 1KGP cluster. Like PUR, they fall
  between Europeans and Africans, even though their labels are split across PUR,
  TSI and IBS (Fig. 3A). The representation captures a distinct profile that the
  forced 24-way label hides.
- Proposed use: flag out-of-distribution individuals as a complement to ensemble
  disagreement (Paper p.1473).

## In the code

- `inference.py` saves `last_hidden_layer` (n_samples × 100) in each
  `*_model{fold}_{rep}_infered.npz` ([inference.py:213-224](../../Dietnet_inference/inference.py#L213-L224)).
- No script in the inference directory performs the PCA/projection. It has to be done
  downstream (unverified: the training directory may contain one).

## See also
- [15-model ensemble](ensemble.md)
- [Populations](../entities/populations.md)
