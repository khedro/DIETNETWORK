---
title: Web platform (backend, frontend, data governance)
type: code
sources: [code]
updated: 2026-10-30
---

# Web platform

Inference-as-a-service on top of the released ensemble: users register, upload
VCF/bgen/PLINK, and get predictions. It **never trains**. Specified in
[deployPlan.md](../../deployPlan.md) and documented in [DEPLOYMENT.md](../../DEPLOYMENT.md).
Branch `webPlatform`.

## Topology

7 containers on one VM ([docker-compose.yml](../../docker-compose.yml)), split across
two Docker networks: `web` (caddy, frontend, backend — caddy is the only one with
published ports) and `internal` (postgres, redis, worker, beat — no route to the host
network). backend is the only container on both. MailHog is an 8th, dev/local-test/CI-only
container (added by the dev/local-test/test overlays, see [Deployment](deployment.md));
production sends mail through a real SMTP relay instead. *(Corrected 2026-10-30: this
page said 8 + MailHog = 9; the base compose file has 7 services.)*

A drawn version of this topology, with a per-protocol card for every link and a
walk-through of one job, is in the "DietNetwork Topology" Claude artifact
(<https://claude.ai/artifact/9cUFNbHGJvhBA8oHjr3Ybc>, private to its owner).

```
                              Internet
                                 │
                           ┌─────▼─────┐
                           │   caddy   │  reverse proxy, TLS
                           │ (web net) │  only container with published ports
                           └──┬─────┬──┘
               everything else│     │/api/*
                               ▼     ▼
                     ┌──────────────┐ ┌───────────────┐
                     │   frontend   │ │    backend    │  FastAPI
                     │  (SvelteKit) │ │   (FastAPI)    │  (auth, uploads, /jobs, /download)
                     │  (web net)   │ │ (web+internal) │
                     └──────────────┘ └───┬───────┬────┘
                                            │        │
                              SQL (asyncpg) │        │ celery_app.send_task(...)
                              + SMTP        │        │ (Celery protocol over Redis, NOT HTTP)
                                            │        ▼
                                            │   ┌──────────┐
                                            │   │  redis   │  broker + queue
                                            │   │(internal)│
                                            │   └───┬───▲──┘
                                            │       │   │
                                            │dequeue│   │beat pushes (LPUSH),
                                            │       ▼   │once a day
                                            │  ┌────────┐ ┌────────┐
                                            │  │ worker │ │  beat  │  no other
                                            │  │(Celery)│ │(Celery)│  connection
                                            │  │(internal)│(internal)│  in the system
                                            │  └───┬────┘ └────────┘
                                            │ SQL+SMTP│
                                            ▼        ▼
                              ┌─────────────────────────┐   single container, one DB --
                              │         postgres          │   2 SQL connections in
                              │         (internal)          │   (backend via asyncpg,
                              └─────────────────────────┘   worker via psycopg2)

                                            (SMTP, from backend and worker above)
                                            ▼
                                       ┌───────────┐
                                       │  mailhog  │  dev/local-test/CI only;
                                       │(internal) │  a real SMTP relay in production
                                       └───────────┘
```

**`beat` has exactly one connection: to `redis`.** It's a pure scheduler (its
container command is just `celery ... beat`) — once a day (`crontab(hour=3, minute=0)`
in `celery_app.py`) it pushes the `cleanup_expired_jobs` task onto the `maintenance`
queue and does nothing else. It never touches Postgres. `worker` is subscribed to
**both** queues (`-Q inference,maintenance`), so it's `worker` — after dequeuing that
task from Redis — that actually runs the cleanup and does the SQL deletes shown above.

Every arrow above shows the **connection initiator** (who dials whom), not one-way data
flow — TCP connections are full-duplex, so a response always travels back over the same
connection the request came in on. E.g. `caddy → frontend` means Caddy opens the
connection and frontend never opens one to Caddy, not that frontend's HTML response
doesn't flow back along it.

**`frontend` and `backend` are two independent upstreams, not a chain.** Caddy picks
one or the other per request based on the URL path (`/api/*` vs. everything else) —
there is no `frontend` → `backend` link anywhere in this system. Every API call
(login, upload, job status, download) is made by the browser's own JavaScript
directly to `backend` through Caddy; `frontend`'s only job is serving that JS once.

Only the browser-facing edge is FastAPI/HTTP. Everything behind it uses each
service's native protocol, not REST calls between containers:

| Link | Protocol |
|---|---|
| Browser → Caddy → backend | HTTP, FastAPI endpoints (`/auth/*`, `/uploads`, `/jobs/*`); the browser's own JS calls these directly, not `frontend` |
| Browser → Caddy → frontend | HTTP (serves the built SvelteKit app; everything not matching `/api/*`) |
| frontend → backend | **No such link.** Two independent upstreams behind Caddy, never talk to each other. |
| backend → worker | **Not HTTP.** `celery_app.send_task(...)` pushes a message (task name + job ID) onto Redis; the worker dequeues it. No FastAPI on either side. |
| backend → redis (downloads) | A Lua `EVAL` on a sorted set ([concurrency.py](../../backend/app/concurrency.py)): atomically drops expired slots, counts, and takes a slot if fewer than `MAX_CONCURRENT_DOWNLOADS` = 9 are in use. Slots expire after 600 s. |
| backend ↔ worker (files) | **Not a network link.** The same host folder is bind-mounted at `/data` in backend, worker and beat. backend writes the upload to `/data/<user>/<job>/raw`; worker reads it and writes `results/`; backend later zips `results/`. The queue message never carries the file. |
| beat → worker | **Not direct at all.** `beat` only pushes a scheduled task message onto Redis once a day; `worker` (subscribed to the same `maintenance` queue) dequeues and runs it. |
| backend/worker → postgres | SQL (asyncpg from backend, psycopg2 from worker — different drivers, same DB). `beat` never connects to postgres. |
| backend/worker → mailhog / SMTP relay | SMTP, not HTTP |
| worker → infer.sh | **Not Celery either.** A plain `subprocess.run(["bash", ...])` child process inside the worker container — same filesystem, same `/data` mount, no network hop. Traced in detail below. |

### What "Celery protocol over Redis" actually is

No bespoke wire protocol — it's plain Redis commands. Confirmed by reading
`kombu/transport/redis.py` (the library Celery uses) inside the running `worker`
container: each queue (`inference`, `maintenance`) is just a **Redis List** named
after the queue.

- **Producer** (`backend` on `send_task(...)`, or `beat` on its daily schedule firing):
  `LPUSH <queue> <json task message>` — pushes onto the left end.
- **Consumer** (`worker`): a blocking `BRPOP inference maintenance <timeout>` —
  blocks the connection open until either list has something, then atomically pops
  from the **right** end.

Left-push + right-pop = FIFO, across both queues on one blocking call. The JSON
payload (task name, args, task id) is Celery/kombu's own message format; the actual
transport is bog-standard Redis RESP over a plain TCP connection — not a separate
protocol Celery invented. This is the concrete mechanism behind every "Celery
protocol over Redis, NOT HTTP" label above, for both `backend → worker` and
`beat → worker`.

## Inference execution trace (inside the `worker` container)

Once `worker` dequeues the task, everything below happens in-process, in that one
container — no further network hop until the final SQL commit / SMTP send back out:

```
                                           ┌─────────────┐
                                           │   worker    │  Celery process,
                                           │ (internal)  │  concurrency = N
                                           └──────┬──────┘
                                                   │ runs entirely INSIDE
                                                   │ this one container
                                    ┌──────────────▼──────────────┐
                                    │   run_inference_job(job_id)   │
                                    │   (worker/worker/tasks.py)    │
                                    └──────────────┬──────────────┘
                                                   │
                     subprocess.run(["bash", "infer.sh", ...])  ← pipeline.run_infer()
                                                   │
                                    ┌──────────────▼──────────────┐
                                    │        infer.sh               │
                                    │  1. plink --extract dietnet   │
                                    │     SNPs, --real-ref-alleles  │
                                    │  2. plink --bmerge dummy      │
                                    │     sample (fills missing     │
                                    │     SNPs so shape matches)    │
                                    │  3. plink --recode A          │
                                    │     (additive 0/1/2 dosage)   │
                                    │  4. inference_dataset.py      │
                                    │     → one .hdf5               │
                                    │  5. for fold in 1..5:         │
                                    │       for rep in 1..3:        │
                                    │         inference.py           │
                                    │         (15 python procs,     │
                                    │          sequential)          │
                                    │  6. inference_combine_results │
                                    │     .py → predictions.txt     │
                                    └───────────────────────────────┘
                                                   │
                                    back in tasks.py: build_results_table,
                                    write_job_log, job.status="done", commit
                                    (SQL → postgres), then send_job_completed_email
                                    (SMTP → mailhog / relay)
```

See [Worker pipeline](worker-pipeline.md) and [Inference pipeline](inference-pipeline.md)
for the full guardrail list and `infer.sh` argument/output details.

## Components

| Dir | Role |
|---|---|
| `backend/` | FastAPI on uvicorn. Routers `auth`, `uploads`, `jobs` ([main.py](../../backend/app/main.py)); `/health`; Alembic owns the schema ([DATABASE.md](../../DATABASE.md)); `concurrency.py` = Redis sliding-window cap on result downloads (429 above `MAX_CONCURRENT_DOWNLOADS` = 9). Uploads are refused with `409` while the user has a queued or running job ([uploads.py:92](../../backend/app/routers/uploads.py#L92)). Downloads are `POST /jobs/{id}/download` with a user-chosen password (8–128 chars); [results_zip.py](../../backend/app/results_zip.py) streams an AES-256 zip (pyzipper) of `results/`. The old unencrypted `GET` returns `405` |
| `worker/` | Celery tasks: [worker pipeline](worker-pipeline.md), cleanup, emails. `CELERY_WORKER_CONCURRENCY` = 9 |
| `frontend/` | SvelteKit (Node adapter, port 3000; pages server-rendered, no server-side data loading): signup/login with Turnstile CAPTCHA, drag-and-drop upload (VCF, bgen, PLINK; the homepage lists all three since `e54b406`), job dashboard with queue position, job page with overlap warning and the password form for the encrypted download. The predictions table is **not** shown in the UI; it is in the zip and in `GET /jobs/{id}` |
| `infra/` | Pulumi (Python, OpenStack): network, security groups, encrypted Cinder volume, VM, cloud-init |
| `ops/` | `fetch_zenodo_models.sh` (models baked into the worker image at build time), systemd-timer cleanup, [usage_stats.sql](../../ops/usage_stats.sql) ([usage statistics](usage-statistics.md)) |

## Security and governance (from deployPlan)

argon2id passwords; email verification before login or upload; server-side CAPTCHA
plus login rate limiting; consent checkbox; TLS; encrypted-at-rest volume; raw
genotypes deleted after success; everything purged at 30 days (job rows and their
counts are kept for [usage statistics](usage-statistics.md)); results downloaded only
as an AES-256 zip under a password the user picks and the server never stores; audit
logging; Canadian data residency. **REB/privacy sign-off is still an open item for the
PI.**

## See also
- [Deployment](deployment.md)
- [Worker pipeline](worker-pipeline.md)
- [Usage statistics](usage-statistics.md)
- [Testing](testing.md)
- [Repo docs](../sources/repo-docs.md)
