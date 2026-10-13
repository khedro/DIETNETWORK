---
title: Web platform (backend, frontend, data governance)
type: code
sources: [code]
updated: 2026-10-09
---

# Web platform

Inference-as-a-service on top of the released ensemble: users register, upload
VCF/bgen/PLINK, and get predictions. It **never trains**. Specified in
[deployPlan.md](../../deployPlan.md) and documented in [DEPLOYMENT.md](../../DEPLOYMENT.md).
Branch `webPlatform`.

## Topology

8 containers on one VM ([docker-compose.yml](../../docker-compose.yml)), split across
two Docker networks: `web` (caddy, frontend, backend — the only one with published
ports) and `internal` (postgres, redis, worker, beat — no route to the host network).
MailHog is a 9th, dev/local-test/CI-only container (added by the dev/local-test/test
overlays, see [Deployment](deployment.md)); production sends mail through a real SMTP
relay instead.

```
                         Internet
                            │
                      ┌─────▼─────┐
                      │   caddy   │  reverse proxy, TLS
                      │ (web net) │  only container with published ports
                      └──┬─────┬──┘
                 ┌────────┘     └────────┐
         ┌───────▼──────┐        ┌───────▼──────┐
         │   frontend   │  HTTP  │   backend    │   FastAPI
         │  (SvelteKit) │───────▶│  (FastAPI)    │   (auth, uploads, /jobs, /download)
         │  (web net)   │ fetch  │ (web+internal)│
         └──────────────┘        └───┬───────┬──┘
                                      │        │
                        SQL (asyncpg) │        │ celery_app.send_task(...)
                                      │        │ (Celery protocol over Redis, NOT HTTP)
                             ┌────────▼─┐    ┌─▼────────┐
                             │ postgres │    │  redis   │  broker + queue
                             │(internal)│    │(internal)│
                             └──────────┘    └───┬───┬──┘
                                                  │   │
                                     dequeue task │   │ same broker
                                                  │   │
                                           ┌───────▼┐ ┌▼────────┐
                                           │ worker │ │  beat   │  daily cron:
                                           │(Celery)│ │(Celery) │  30-day cleanup
                                           │(internal)│(internal)│
                                           └───┬────┘ └────┬────┘
                              SQL (psycopg2)   │           │ SQL
                                     ┌─────────▼───────────▼┐
                                     │       postgres        │ (same DB, shared)
                                     └────────────────────────┘
                                           │
                                  SMTP     │  (worker + backend both send mail)
                                     ┌─────▼─────┐
                                     │  mailhog  │  (dev/test only; real relay in prod)
                                     └───────────┘
```

Only the browser-facing edge is FastAPI/HTTP. Everything behind it uses each
service's native protocol, not REST calls between containers:

| Link | Protocol |
|---|---|
| Browser → Caddy → backend | HTTP, FastAPI endpoints (`/auth/*`, `/uploads`, `/jobs/*`) |
| Caddy → frontend | HTTP (serves the built SvelteKit app) |
| backend → worker | **Not HTTP.** `celery_app.send_task(...)` pushes a message onto Redis; the worker dequeues it. No FastAPI on either side. |
| backend/worker → postgres | SQL (asyncpg from backend, psycopg2 from worker/beat — different drivers, same DB) |
| backend/worker → mailhog / SMTP relay | SMTP, not HTTP |

## Components

| Dir | Role |
|---|---|
| `backend/` | FastAPI. Routers `auth`, `uploads`, `jobs` ([main.py](../../backend/app/main.py)); `/health`; Alembic owns the schema; `concurrency.py` = Redis sliding-window cap on result downloads (429 above `MAX_CONCURRENT_DOWNLOADS` = 9) |
| `worker/` | Celery tasks: [worker pipeline](worker-pipeline.md), cleanup, emails. `CELERY_WORKER_CONCURRENCY` = 9 |
| `frontend/` | SvelteKit: signup/login with Turnstile CAPTCHA, drag-and-drop upload, job dashboard with queue position, results view with overlap warning |
| `infra/` | Pulumi (Python, OpenStack): network, security groups, encrypted Cinder volume, VM, cloud-init |
| `ops/` | `fetch_zenodo_models.sh` (models baked into the worker image at build time), systemd-timer cleanup |

## Security and governance (from deployPlan)

argon2id passwords; email verification before login or upload; server-side CAPTCHA
plus login rate limiting; consent checkbox; TLS; encrypted-at-rest volume; raw
genotypes deleted after success; everything purged at 30 days; audit logging; Canadian
data residency. **REB/privacy sign-off is still an open item for the PI.**

## See also
- [Deployment](deployment.md)
- [Repo docs](../sources/repo-docs.md)
