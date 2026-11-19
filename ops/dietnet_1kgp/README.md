# 1KGP fold partition for the inference quality-control step

`Dietnet_inference/infer.sh` checks every upload by running the 15 models on
1KGP using only the SNPs the upload shares with the panel. Each model is scored
on its own **test fold**, read from:

    1KGP_2322inds_24pops_230Ksnps_parition.npz   (key `folds_indexes`, as written by
                                                  Dietnet_train_and_evaluate/partition_data.py)

This file is not on Zenodo. Put the partition the released `DN_MODELS` were
trained with in this directory (it's ~34 KB); the worker image build copies it
into `/opt/dietnet/files/1KGP/` and fails with a clear error if it's missing.

It has to be the training partition. Any other split scores models partly on
samples they were trained on, and the 95% accuracy gate becomes too lenient.

The other two 1KGP files are fetched or derived at build time by
`ops/scripts/fetch_zenodo_models.sh`: the genotypes hdf5 (from
`Dietnet_training.tar.gz`) and `1000G.2322samples.labels.txt` (generated from
that hdf5's `samples` / `class_labels`).
