---
title: Overview
type: overview
sources: [paper, code]
updated: 2026-09-28
---

# DIETNETWORK — overview

This repo implements the framework in
[Rochefort-Boulanger et al., AJHG 2026](sources/publication.md): predict a person's
genetic ancestry, as one of **24 1KGP populations**, from unphased SNP genotypes,
in a way that generalizes across biobanks and can be explained.

## The idea in five lines

1. **Fat data.** ~230k SNPs, ~2.3k training people. A normal MLP's first layer would
   overfit badly.
2. **Diet Network.** An auxiliary net *generates* those first-layer weights from each
   SNP's per-population genotype frequencies
   ([architecture](concepts/diet-network-architecture.md), [embedding](concepts/snp-embedding.md)).
3. **Input dropout 0.995** plus mean-imputation and rescaling make the model tolerate
   datasets that lack most of its SNPs ([input dropout](concepts/input-dropout.md),
   [missing SNPs](concepts/missing-snp-handling.md)).
4. **15-model ensemble** reports 15 votes, not one label. Disagreement and the
   [latent space](concepts/latent-representations.md) flag admixed or
   out-of-reference individuals ([ensemble](concepts/ensemble.md)).
5. **Explainable.** DeepLift attributions with a genotype-average baseline pick out
   high-F_ST SNPs and reproduce the population-structure blocks
   ([attribution](concepts/feature-attribution.md), [baselines](concepts/attribution-baselines.md),
   [F_ST](concepts/fst.md)).

## Three layers of code

| Layer | Directory | Page |
|---|---|---|
| Research: train and evaluate | `Dietnet_train_and_evaluate/` | [training pipeline](code/training-pipeline.md) |
| Released tool: inference | `Dietnet_inference/` + Zenodo files | [inference pipeline](code/inference-pipeline.md) |
| Service: web platform (branch `webPlatform`) | `backend/ worker/ frontend/ infra/ ops/` | [web platform](code/web-platform.md), [worker](code/worker-pipeline.md), [deployment](code/deployment.md) |

## What to be careful about

- Input must be **GRCh38**, with `chr<c>:<pos>:<ref>:<alt>` IDs and alleles harmonized
  to the panel.
- Fewer than 1,000 overlapping SNPs means the result is unreliable.
- There are no North African or West Asian reference populations. Those individuals
  get forced into the nearest labels, often PUR/TSI/IBS.
- PUR is the model's fallback class.
- See [paper vs code](analysis/paper-vs-code.md) for doc errors and missing pieces.

## See also
- [Index](index.md) · [Log](log.md) · [Schema](CLAUDE.md)
