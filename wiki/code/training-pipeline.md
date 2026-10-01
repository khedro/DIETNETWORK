---
title: Training pipeline (Dietnet_train_and_evaluate/)
type: code
sources: [code, paper]
updated: 2026-09-28
---

# Training pipeline

[Dietnet_train_and_evaluate/](../../Dietnet_train_and_evaluate/) retrains Diet
Network (or a plain MLP) for classification or regression. Four preparation
scripts produce files that `train.py` consumes, one fold per run.

## Flow

```
genotypes.tsv + labels.tsv
   └─ create_dataset.py ─────────────► dataset.hdf5  (inputs, class_labels, class_label_names, samples, snp_names, [regression_labels])
        └─ partition_data.py ────────► partition.npz  (folds_indexes[fold] = [train, valid, test])
        ├─ compute_input_features_statistics.py ─► stats.npz (means_by_fold, sd_by_fold)
        └─ generate_embedding.py ────► embedding.npz (emb: folds × SNPs × 3·classes)
              └─ train.py --which-fold k ► RESULTS_<id>/best_model.pt, last_model.pt, predictions
```

- **Partition** defaults: 5 folds, seed 23, train/valid ratio 0.75 within the non-test
  data. One fold is test (20%), and the rest splits 60/20, matching the paper's
  60/20/20 (Paper p.1463–1464).
- **Statistics** are computed on each fold's training samples, ignoring missing (-1)
  ([dataset_utils.py:159-181](../../Dietnet_train_and_evaluate/helpers/dataset_utils.py#L159-L181)).
- **Embedding**: see [SNP embedding](../concepts/snp-embedding.md).

## train.py

[train.py](../../Dietnet_train_and_evaluate/train.py) (`main()`; the `train()` function
below it is legacy and not called).
- Args: `--exp-path --exp-name --config --dataset --partition --embedding
  --input-features-stats --task {classification,regression} --which-fold
  [--model Dietnet|Mlp] [--normalize] [--resume-training]`.
- Loads **all** genotypes into RAM as int8 ([train.py:195-206](../../Dietnet_train_and_evaluate/train.py#L195-L206)).
- Each step: mean-impute, standardize if `--normalize`, forward, loss (CrossEntropy or
  MSE), step **both** optimizers ([mainloop_utils.py:14-77](../../Dietnet_train_and_evaluate/helpers/mainloop_utils.py#L14-L77)).
- After each epoch: multiply every LR by `learning_rate_annealing`; early stopping on
  validation with `patience`; save best and last checkpoints.
- Finally tests the best checkpoint on the fold's test set.
- Config keys actually read: `seed`, `batch_size`, `epochs`, `patience`,
  `learning_rate_annealing`, `input_dropout`, `dropout_main`, `nb_hidden_u_aux`,
  `nb_hidden_u_main`, `uniform_init_limit`, `lr_aux`, `lr_main`. The comment at
  [train.py:74-85](../../Dietnet_train_and_evaluate/train.py#L74-L85) says `learning_rate`, which is stale.
- Optional Comet.ml logging (commented as possibly broken).

## Paper's setup (Paper p.1463–1464)

15 models (5 folds × 3 repeats), input dropout 0.995, genotype standardization,
hyperparameters tuned on validation. 10 GB RAM, 8 CPUs, one A100 40 GB; 2,329 epochs
≈ 22 min per model.

## From checkpoint to released model

Inference needs `weights_model{f}_{r}.pt`, `snps_emb_model{f}.npz` (key `emb`, 2-D)
and `norm_stats_model{f}.npz` (keys `mean`, `std`). Training produces a 3-D
per-fold embedding and stats with keys `means_by_fold`/`sd_by_fold`. So a per-fold
export step is needed; it was not found in the repo (see
[paper vs code](../analysis/paper-vs-code.md)). This only matters for retraining; the
web platform uses the released files as-is.

## Legacy code

`mainloop_utils.py` still contains Theano-era helpers (`load_theano_model`,
`create_disc_model_multi_gpu`) that reference `model.CombinedModel`/`Discrim_net`,
which no longer exist, and hard-code `n_targets=26` (the pre-merge population count).
They would fail if called.

## See also
- [Diet Network architecture](../concepts/diet-network-architecture.md)
- [Input dropout](../concepts/input-dropout.md)
