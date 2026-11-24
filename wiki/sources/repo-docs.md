---
title: Repository docs (README, DEPLOYMENT, deployPlan, TESTING, DATABASE)
type: source
sources: [code]
updated: 2026-10-30
---

# Repository docs

Five prose documents in the repo. Useful context, but code and paper win when
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

## [TESTING.md](../../TESTING.md)
Test plan for the pre-flight checks and the queue: manual steps (positive control,
fixtures 2a–2d, FCFS queue, download cap), then the automated `tests/` suite that
runs them all against an isolated stack ([testing](../code/testing.md)). Ingested
2026-10-30. **Two stale parts:** its "Results" table is from the 2026-09-18 run (6 unit
tests then, 23 now; checks added since are missing), and "Out of scope here" still says
result encryption is not implemented, though the AES zip landed in `6e1600d`. See
[paper vs code](../analysis/paper-vs-code.md#docs-vs-code).

## [DATABASE.md](../../DATABASE.md)
How `backend/app/models.py` (async), `worker/worker/db.py` (a hand-kept sync mirror)
and Alembic migrations relate, plus the full schema. Ingested 2026-10-30. Key points:
`alembic upgrade head` runs on every backend boot; the worker's mirror must be
updated by hand when `users` or `jobs` change (two past incidents came from drift);
the `jobs` table now documents `sample_count` and points at
[usage statistics](../code/usage-statistics.md).

## See also
- [Publication](publication.md)
- [Overview](../overview.md)
