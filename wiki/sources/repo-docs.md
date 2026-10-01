---
title: Repository docs (README, DEPLOYMENT, deployPlan)
type: source
sources: [code]
updated: 2026-09-28
---

# Repository docs

Three prose documents in the repo. Useful context, but code and paper win when
they disagree; see [paper vs code](../analysis/paper-vs-code.md).

## [README.md](../../README.md)
- Describes the model (24 1KGP populations, 15-model ensemble, Zenodo record 16943452).
- Installation: Python 3.11.5, `Dietnet_inference/dietnet_infer_python3115_requirements.txt`, PLINK 1.9.
- Inference input: PLINK .bed/.bim/.fam on GRCh38, ideally with >10%-missing SNPs removed.
- Lists the output files ([inference pipeline](../code/inference-pipeline.md)).
- Documents the training preparation CLIs: `create_dataset.py`, `partition_data.py`,
  `compute_input_features_statistics.py`, `generate_embedding.py`
  ([training pipeline](../code/training-pipeline.md)).
- **`infer.sh` usage:** upstream (commit `d69d184`) had the wrong argument order.
  **Corrected in the fork on 2026-09-28**, with an inline correction note in the README.
- **Still open:** it links the bioRxiv preprint rather than the AJHG paper, also
  inherited from upstream. See [paper vs code](../analysis/paper-vs-code.md#docs-vs-code).

## [deployPlan.md](../../deployPlan.md)
The design brief for the web platform: inference only, CPU only, on Arbutus
(Alliance OpenStack) via Pulumi, SvelteKit + FastAPI + Celery + Postgres + Redis + Caddy.
Its "critical facts" are all confirmed by the code: PLINK input only, 15 sequential
models, the real `infer.sh` argument order, the < 1000 SNP-overlap reliability rule,
and models baked in from Zenodo. It also sets the data-governance rules
(PIPEDA / Quebec Law 25, 30-day deletion, REB sign-off).

## [DEPLOYMENT.md](../../DEPLOYMENT.md)
Operator guide for what was built: the layout (`backend/`, `worker/`, `frontend/`,
`infra/`, `ops/`), the three compose modes (dev, local-test/ICM, Arbutus),
the Pulumi config/secrets table, concurrency caps, and open items for the PI.
See [web platform](../code/web-platform.md) and [deployment](../code/deployment.md).

## See also
- [Publication](publication.md)
- [Overview](../overview.md)
