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

## [2026-10-20] update | web-platform diagram extended through infer.sh
Replaced the container-topology diagram in code/web-platform.md with one that also
traces the inference path: backend's send_task → Redis → worker dequeue →
run_inference_job (in-process) → subprocess "bash infer.sh" → its 6 internal steps
(plink extract/merge/recode, inference_dataset.py, 15×inference.py, combine_results.py)
→ back into tasks.py for the results table/job log/DB commit. Confirmed against
Dietnet_inference/infer.sh and worker/worker/{tasks,pipeline}.py directly. Added a
cross-link from code/worker-pipeline.md to this diagram.

## [2026-10-20] update | web-platform diagram split, beat/mailhog restored
The previous entry's merge of the container topology and the infer.sh trace into one
diagram dropped beat/mailhog for readability and became hard to follow. Reverted
code/web-platform.md's Topology diagram to the original full 9-container version
(caddy/frontend/backend/postgres/redis/worker/beat/mailhog, all networks and protocols
intact) and added the infer.sh trace as its own separate "Inference execution trace"
diagram right after it, rather than merging the two.

## [2026-10-20] update | web-platform diagram: single postgres box
User caught that the topology diagram drew postgres twice (once near backend, once
near worker/beat, labeled "same DB, shared"), reading as two databases. Confirmed via
docker-compose.yml there is exactly one `postgres:` service. Redrew with a single
postgres box receiving all 3 SQL connections (asyncpg from backend, psycopg2 from
worker/beat) and mailhog as its own separate SMTP sink below it, not chained through
postgres.

## [2026-10-20] update | web-platform diagram: removed false frontend->backend link
User caught a real error: the topology diagram drew `frontend --HTTP fetch--> backend`,
implying the frontend container calls the backend. It never does -- there are no
+page.server.ts/+page.ts files in frontend/src/routes (checked directly), so every API
call (login, upload, job status, download) is made by the browser's own JS straight to
backend through Caddy; frontend's only role is serving that JS once. Redrew Caddy
fanning out to frontend and backend as two independent, parallel upstreams with no
edge between them, and fixed the protocol table to match.

## [2026-10-20] update | web-platform diagram: arrow-direction legend
Added a note under the topology diagram in code/web-platform.md clarifying that each
arrow shows the connection initiator (who dials whom), not one-way data flow -- TCP is
full-duplex, so a response always travels back over the same connection the request
came in on. Raised by the user after confirming Caddy<->frontend is bidirectional.

## [2026-10-20] update | web-platform diagram: beat never connects to postgres
Found while walking the user through the internal-network connections: the diagram
drew beat -> postgres directly (SQL), which is wrong. Confirmed in worker/worker/
celery_app.py -- beat's container command is just `celery ... beat` (pure scheduler);
it only pushes the cleanup_expired_jobs task onto redis's "maintenance" queue once a
day (crontab(hour=3)). worker is subscribed to both "inference" and "maintenance"
queues, so it's worker that dequeues and actually runs the cleanup + SQL deletes.
beat's only connection in the whole system is to redis. Fixed the diagram and protocol
table accordingly.

## [2026-10-20] ingest | kombu redis transport (third-party, read in-container)
Added a "What 'Celery protocol over Redis' actually is" subsection to code/web-platform.md.
Read kombu/transport/redis.py directly inside the running worker container (not part of
this repo, so no relative file link -- cited as a third-party library instead): each
Celery queue is a Redis List; producers LPUSH a JSON task message, worker consumes via
blocking BRPOP on both queues at once. Grounds every "Celery protocol over Redis, NOT
HTTP" label already in the topology diagram/table (backend->worker and beat->worker).

## [2026-10-27] update | web-platform diagram: beat's arrow pointed the wrong way
Caught while comparing the wiki diagram against a Claude-artifact redraw of the same
topology: the ASCII diagram drew `redis -> beat` (dequeue-style arrow, labeled "same
broker"), but beat never receives anything from Redis -- it only ever pushes the daily
cleanup task onto it. The prose right below the diagram and the protocol table already
said this correctly; only the arrowhead itself was stale from before the 2026-10-20
beat/postgres fix. Flipped it to `beat -> redis`, relabeled "beat pushes (LPUSH), once
a day."
