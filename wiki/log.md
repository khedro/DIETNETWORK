# Wiki log

Append-only. Newest at the bottom. `grep "^## \[" wiki/log.md | tail -5`

## [2026-09-28] init | Wiki created from llm-wiki.md
Schema written to `wiki/CLAUDE.md` (sources / concepts / entities / code / analysis;
frontmatter; page-number citations for the paper, file links for the code).

## [2026-09-28] ingest | DIETNETWORK_Publication.pdf
All 17 pages read. Created sources/publication, 8 concept pages, 3 entity pages.

## [2026-09-28] ingest | Codebase (partial)
Read: README.md, DEPLOYMENT.md, deployPlan.md, docker-compose.yml;
Dietnet_inference/{infer.sh, inference.py, inference_dataset.py, inference_combine_results.py};
Dietnet_train_and_evaluate/{train.py, generate_embedding.py, compute_input_features_statistics.py (partial),
helpers/model.py, helpers/mainloop_utils.py, helpers/dataset_utils.py};
worker/worker/{pipeline.py, tasks.py, config.py, cleanup.py}; backend/app/main.py.
Pipeline and tasks reflect uncommitted working-tree changes.
Created 5 code pages and analysis/paper-vs-code.
**Limitation:** shell was unavailable, so the repo could not be listed. Not yet
ingested: partition_data.py, create_dataset.py, task/model handlers, backend routers,
frontend, infra, ops, worker tests, any attribution/analysis scripts. Next step: a
lint pass with a full file listing to fill the "Gaps" section of paper-vs-code.

## [2026-09-28] query | Is the README really wrong? Caddy ports? Training/inference mismatch?
- README `infer.sh` usage verified wrong via git: introduced upstream in `d69d184`,
  same on `origin/main`, `infer.sh` unchanged since. Not a fork error.
- Caddy 8080/8443 in base compose is intentional for local-server testing; noted to
  switch to 80/443 before Arbutus.
- Training→inference export gap reclassified: irrelevant to the web platform (uses
  released Zenodo files); only matters for retraining.

## [2026-09-28] update | README infer.sh usage corrected
README.md now documents the real 5-argument `infer.sh` order, warns that the output
prefix must be relative, and carries a "Correction (fork)" note citing upstream commit
`d69d184`. Updated paper-vs-code, repo-docs, inference-pipeline. bioRxiv link still open.

## [2026-10-01] ingest | specifications.docx
Team spec (French): user flow, processing, final results, figures. Checked each item
against backend routers (uploads, jobs), frontend job/upload pages, worker pipeline.
Created analysis/spec-status. Main gaps: results table with consensus and missing rate,
log file, encrypted zip, figures, 1KGP reference data, chr+pos ID rewrite.

## [2026-10-09] update | web-platform topology expanded
Replaced the one-line Topology diagram in code/web-platform.md with the full 8-container
layout (caddy/frontend/backend/worker/beat/postgres/redis + dev-only mailhog), the `web`
vs `internal` network split, and a per-link protocol table. Confirms only the
browser-facing edge is FastAPI/HTTP; backend→worker is Celery over Redis (not HTTP),
DB access is SQL, mail is SMTP. Verified network/service names against docker-compose.yml
and confirmed mailhog is absent from the production base compose file (dev/local-test/
tests overlays only).
