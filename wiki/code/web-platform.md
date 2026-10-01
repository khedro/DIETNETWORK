---
title: Web platform (backend, frontend, data governance)
type: code
sources: [code]
updated: 2026-09-28
---

# Web platform

Inference-as-a-service on top of the released ensemble: users register, upload
VCF/bgen/PLINK, and get predictions. It **never trains**. Specified in
[deployPlan.md](../../deployPlan.md) and documented in [DEPLOYMENT.md](../../DEPLOYMENT.md).
Branch `webPlatform`.

## Topology

```
Internet → Floating IP → Caddy (TLS) → SvelteKit frontend
                                     → FastAPI backend → Postgres
                                                       → Redis → Celery worker(s) → encrypted volume
                                                                 Celery beat (30-day cleanup)
```

Postgres and Redis publish no ports and sit only on the `internal` network
([docker-compose.yml](../../docker-compose.yml)).

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
