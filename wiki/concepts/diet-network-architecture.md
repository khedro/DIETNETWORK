---
title: Diet Network architecture
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# Diet Network architecture

Two networks trained together. A **main network** classifies an individual from
their genotypes. An **auxiliary network** generates the main network's enormous
first-layer ("fat layer") weights from a small per-SNP embedding, so the parameter
count no longer scales as SNPs × hidden units. This is how it copes with the
"fat-data" problem: ~230k inputs, ~2.3k samples (Paper p.1462–1463, Fig. S1;
original design: Romero et al., ICLR 2017).

## Shapes (as implemented)

```
SNP embedding E            (n_snps × 72)      72 = 24 populations × 3 genotypes
   │  column-wise L2 normalize
   ▼
Aux net   Linear(72→100, no bias) → tanh → Linear(100→100, no bias) → tanh
   │  output (n_snps × 100), transposed
   ▼
Fat-layer weights W_fat    (100 × n_snps)

Genotypes x (n_snps)  → input dropout
   → F.linear(x, W_fat, fat_bias) → ReLU → BatchNorm → dropout     (fat layer, 100)
   → Linear(100→100)              → ReLU → BatchNorm → dropout     (hidden, 100)
   → Linear(100→24)                                                (logits)
```

- Aux net: [model.py:13-98](../../Dietnet_train_and_evaluate/helpers/model.py#L13-L98). Hidden
  sizes come from config `nb_hidden_u_aux`; weights initialized uniform(±`uniform_init_limit`).
- Main net: [model.py:101-265](../../Dietnet_train_and_evaluate/helpers/model.py#L101-L265). Note the
  order **ReLU then BatchNorm**, and the fat layer has its own `fat_bias`.
- Glue: `DietNetwork.forward` recomputes the fat-layer weights from the embedding on
  **every** forward pass during training ([model.py:345-357](../../Dietnet_train_and_evaluate/helpers/model.py#L345-L357)).
- Two Adam optimizers, one per sub-network, with separate learning rates `lr_aux` and
  `lr_main` ([model.py:333-342](../../Dietnet_train_and_evaluate/helpers/model.py#L333-L342)).
- An `Mlp` baseline without the aux net is also available (`--model Mlp`).

## At inference time

[inference.py](../../Dietnet_inference/inference.py) runs the aux net **once** to
materialize `W_fat`, then loads a plain 3-layer MLP (`layers.0` = fat layer) by
renaming the training checkpoint's keys (`make_statedict_main_network`,
[inference.py:239-269](../../Dietnet_inference/inference.py#L239-L269)). The
forward pass returns both the logits and the **last hidden layer** (100-d), which is
saved for [latent-representation](latent-representations.md) analysis.

## Why the embedding matters

The embedding is the per-population genotype frequency of each SNP (see
[SNP embedding](snp-embedding.md)). SNPs with similar population-frequency profiles
get similar fat-layer weights. This ties the parameters to population-genetic
structure, which regularizes the model (Paper p.1463).

## See also
- [Input dropout](input-dropout.md)
- [Training pipeline](../code/training-pipeline.md)
- [Inference pipeline](../code/inference-pipeline.md)
