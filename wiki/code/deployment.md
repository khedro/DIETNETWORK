---
title: Deployment modes
type: code
sources: [code]
updated: 2026-10-30
---

# Deployment modes

One base compose file and three ways to run it
([DEPLOYMENT.md](../../DEPLOYMENT.md)).

| Mode | Command | Differs from production by |
|---|---|---|
| Dev (laptop) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build` | No Caddy/TLS; frontend :5173 and API :8000 are separate origins; MailHog at :8025; CAPTCHA test key |
| Local test (shared server, e.g. ICM) | `./localDeployICM` (wraps the `docker-compose.local-test.yml` overlay) | Ports 8080/8443, self-signed cert, MailHog, CAPTCHA off. Same container topology |
| Arbutus (production) | `cd infra && pulumi up` | — |

## Arbutus via Pulumi

`pulumi up` provisions network, two least-privilege security groups (22 only from
`adminCidr`), an **encrypted** Cinder volume, keypair, floating IP, and one CPU VM.
Cloud-init installs Docker, mounts the volume at `/mnt/data`, clones `gitRepoUrl@gitRef`,
writes `.env` from Pulumi config, and runs `docker compose up -d --build`. Follow
progress in `/var/log/dietnet-bootstrap.log`. Secrets are set only with
`pulumi config set --secret`.

## Data on disk and schema migrations

- Postgres data and the `/data` uploads folder are bind-mounted from
  `${DATA_HOST_PATH}` ([docker-compose.yml:64](../../docker-compose.yml#L64)):
  `/mnt/data/{postgres,uploads}` on Arbutus (cloud-init sets `DATA_HOST_PATH=/mnt/data`,
  [user_data.sh.tmpl:101](../../infra/cloud-init/user_data.sh.tmpl#L101)), `./volumes/`
  locally, `tests/.volumes-test/` for the test suite.
- The backend's entrypoint runs `alembic upgrade head` before the app starts
  ([docker-entrypoint.sh](../../backend/docker-entrypoint.sh)), so a deploy or restart
  applies new migrations by itself. Current head: `5c1d2e7a9b40` (adds
  `jobs.sample_count`, see [usage statistics](usage-statistics.md)).
- **No backup is set up.** Nothing in the repo runs `pg_dump` or snapshots the Cinder
  volume. Losing the volume loses every account, job row and usage statistic. A
  scheduled `pg_dump` or Cinder snapshot, kept on Canadian infrastructure
  ([deployPlan.md](../../deployPlan.md)), is an open item.

## Deployed state (checked 2026-10-30)

- **Local ICM stack** (`dietnetwork` project, 8080/8443 + MailHog): images built
  2026-10-20, database at `5c1d2e7a9b40`, so it runs `e54b406`.
- **Arbutus**: cannot have `e54b406` yet. `webPlatform` was one commit ahead of
  `origin` and cloud-init clones from the repo. Not checked on the VM itself.
- The test suite runs on its own isolated project; see [Testing](testing.md).

## Things to verify by hand

- `volumeType` really is an encrypted type. Nothing in the deploy checks it, and the
  encryption-at-rest guarantee depends on it.
- A domain for a real Let's Encrypt certificate (otherwise the cert is self-signed on
  the floating IP).
- The SMTP relay on port 587 (port 25 is blocked on Alliance cloud).
- **Caddy host ports**: the base `docker-compose.yml` currently uses 8080/8443 on
  purpose, for local-server testing. Change to 80/443 before deploying to Arbutus
  ([paper vs code](../analysis/paper-vs-code.md#docs-vs-code)).

## Scaling

To move the worker to its own VM: expose Postgres and Redis on the private network,
add the new VM to `internal_sg`, and point `REDIS_URL`/`DATABASE_URL_SYNC` at them.
No code changes are needed.

## See also
- [Web platform](web-platform.md)
- [Testing](testing.md)
- [Usage statistics](usage-statistics.md)
