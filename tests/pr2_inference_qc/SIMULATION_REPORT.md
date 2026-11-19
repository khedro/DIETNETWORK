# 12-user browser simulation report

Total time 575 s. Checks: **181/181 passed**.

12 users, 18 jobs (repeat submissions: user1 x3, user4 x2, user8 x2, user11 x2, user12 x2).

## Jobs

| Job | Format | Upload MB | Uploaded at (s) | Queue wait (s) | Job run (s) | Download (s) | Attempts | Outcome |
|---|---|---:|---:|---:|---:|---:|---:|---|
| user1#1 | plink | 11.3 | 8.8 | 0.0 | 208.1 | 0.3 | 1 | done |
| user1#2 | plink | 11.3 | 222.4 | 0.0 | 169.1 | 0.2 | 1 | done |
| user1#3 | plink | 11.3 | 396.2 | 0.0 | 168.0 | 0.8 | 1 | done |
| user2#1 | plink | 11.3 | 8.8 | 0.0 | 211.3 | 0.7 | 1 | done |
| user3#1 | plink | 11.3 | 8.7 | 0.1 | 210.9 | 0.8 | 1 | done |
| user4#1 | plink | 11.3 | 9.0 | 0.0 | 210.8 | 0.3 | 1 | done |
| user4#2 | plink | 11.3 | 223.7 | 0.0 | 168.3 | 0.7 | 1 | done |
| user5#1 | plink | 11.3 | 8.8 | 0.0 | 211.0 | 0.3 | 2 | done |
| user6#1 | plink | 11.3 | 8.9 | 0.0 | 210.5 | 0.7 | 1 | done |
| user7#1 | plink | 11.3 | 8.9 | 0.0 | 210.6 | 0.6 | 1 | done |
| user8#1 | vcf | 56.0 | 9.5 | 209.7 | 166.3 | 0.3 | 1 | done |
| user8#2 | vcf | 56.0 | 387.5 | 0.0 | 165.4 | 0.8 | 1 | done |
| user9#1 | vcf.gz | 6.0 | 8.9 | 0.0 | 210.2 | 0.3 | 2 | done |
| user10#1 | bgen | 21.4 | 9.4 | 0.0 | 210.7 | 0.8 | 1 | done |
| user11#1 | bgen | 21.4 | 9.4 | 207.5 | 169.2 | 0.2 | 1 | done |
| user11#2 | bgen | 21.4 | 391.6 | 0.0 | 166.7 | 0.7 | 1 | done |
| user12#1 | low_overlap | 0.0 | 7.9 | 0.1 | 1.0 | - | - | failed |
| user12#2 | low_overlap | 0.0 | 12.6 | 206.8 | 1.0 | - | - | failed |

## Queue and concurrency

- Job run time: median 209 s, min 165 s, max 211 s.
- Queue wait: median 0.0 s, max 209.7 s.
- Jobs that waited for a slot (> 5 s): user8#1 (210 s), user11#1 (208 s), user12#2 (207 s).
- Delay from a slot freeing to the next queued job starting: user8#1 0.0 s, user11#1 0.0 s, user12#2 0.1 s.
- Peak jobs running at once (from database timestamps): **9** (limit 9).
- Queue positions shown on job pages: {'user8': [1, 2], 'user10': [1], 'user11': [1], 'user12': [3]}.
- Upload order: user12#1, user3#1, user2#1, user1#1, user5#1, user6#1, user7#1, user9#1, user4#1, user10#1, user11#1, user8#1, user12#2, user1#2, user4#2, user8#2, user11#2, user1#3.
- Start order: user12#1, user3#1, user2#1, user1#1, user5#1, user6#1, user7#1, user9#1, user4#1, user10#1, user11#1, user8#1, user12#2, user1#2, user4#2, user8#2, user11#2, user1#3.

## Postgres

| User | Verified | Active | Consented | Jobs in DB | Statuses | Raw deleted |
|---|---|---|---|---:|---|---|
| user1 | True | True | True | 3 | done, done, done | yes, yes, yes |
| user2 | True | True | True | 1 | done | yes |
| user3 | True | True | True | 1 | done | yes |
| user4 | True | True | True | 2 | done, done | yes, yes |
| user5 | True | True | True | 1 | done | yes |
| user6 | True | True | True | 1 | done | yes |
| user7 | True | True | True | 1 | done | yes |
| user8 | True | True | True | 2 | done, done | yes, yes |
| user9 | True | True | True | 1 | done | yes |
| user10 | True | True | True | 1 | done | yes |
| user11 | True | True | True | 2 | done, done | yes, yes |
| user12 | True | True | True | 2 | failed, failed | no, no |

## Emails caught by MailHog

| User | Count | Subjects |
|---|---:|---|
| user1 | 7 | Diet Network Ancestry Platform: your ancestry results are ready ×3; Diet Network Ancestry Platform: your ancestry job has started ×3; Diet Network Ancestry Platform: verify your email |
| user2 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user3 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user4 | 5 | Diet Network Ancestry Platform: your ancestry results are ready ×2; Diet Network Ancestry Platform: your ancestry job has started ×2; Diet Network Ancestry Platform: verify your email |
| user5 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user6 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user7 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user8 | 5 | Diet Network Ancestry Platform: your ancestry results are ready ×2; Diet Network Ancestry Platform: your ancestry job has started ×2; Diet Network Ancestry Platform: verify your email |
| user9 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user10 | 3 | Diet Network Ancestry Platform: your ancestry results are ready; Diet Network Ancestry Platform: your ancestry job has started; Diet Network Ancestry Platform: verify your email |
| user11 | 5 | Diet Network Ancestry Platform: your ancestry results are ready ×2; Diet Network Ancestry Platform: your ancestry job has started ×2; Diet Network Ancestry Platform: verify your email |
| user12 | 5 | Diet Network Ancestry Platform: your ancestry job failed ×2; Diet Network Ancestry Platform: your ancestry job has started ×2; Diet Network Ancestry Platform: verify your email |

## API response times (from the browsers)

| Endpoint | Calls | Median ms | p95 ms | Max ms |
|---|---:|---:|---:|---:|
| `GET /api/auth/me` | 44 | 5 | 9 | 117 |
| `GET /api/auth/verify` | 12 | 6 | 449 | 449 |
| `GET /api/jobs` | 24 | 65 | 684 | 761 |
| `GET /api/jobs/{id}` | 951 | 7 | 17 | 95 |
| `POST /api/auth/login` | 12 | 503 | 717 | 717 |
| `POST /api/auth/signup` | 12 | 868 | 1154 | 1154 |
| `POST /api/jobs/{id}/download` | 18 | 417 | 714 | 714 |
| `POST /api/uploads` | 19 | 1022 | 2214 | 2214 |

Responses with an error status:

- `GET /api/auth/me` → 401: 24
- `GET /api/jobs/{id}` → 404: 1
- `POST /api/jobs/{id}/download` → 429: 2
- `POST /api/uploads` → 409: 1

## Resources (sampled by `docker stats`)

| Container | Peak CPU (% of one core) | Peak memory (MB) |
|---|---:|---:|
| dietnet-e2e-pr2-backend-1 | 114 | 216 |
| dietnet-e2e-pr2-beat-1 | 0 | 56 |
| dietnet-e2e-pr2-edge-1 | 32 | 55 |
| dietnet-e2e-pr2-frontend-1 | 4 | 24 |
| dietnet-e2e-pr2-mailhog-1 | 3 | 10 |
| dietnet-e2e-pr2-postgres-1 | 10 | 73 |
| dietnet-e2e-pr2-redis-1 | 1 | 7 |
| dietnet-e2e-pr2-worker-1 | 8217 | 14039 |

- Host load (1 min) peak: 62.2 on 128 cores.
- Most model processes (`inference.py`) running at once: 9.
- Most jobs inside `infer.sh` at once: 9.
- `/data` peak size: 6235 MB.

## Downloads

- 16 succeeded (expected 16); 2 attempt(s) refused with 429 (the 9-at-once limit) and retried.
- Successful download time: median 0.7 s, max 0.8 s.
- Zip size: median 1.9 MB.

## Findings from the browser

- Selecting or dropping the three PLINK files together submitted for all 4 users (user1, user2, user3, user4).
- user1 opening another user's job: 404, page shows: "Job not found".
- user5, submitting a `.bed` without `.bim`/`.fam`: page shows: "A .bim and a .fam file are required alongside a .bed upload.".
- user7, second upload while a job is active: 409, page shows: "You already have a job in progress. Please wait for it to finish before uploading another.".
- No user was logged out during the run.
- user12 job 1 (should be rejected), page shows: "Only 400 of 229986 Diet Network reference SNPs were found in your data (minimum 1000 required for reliable predictions). This is often caused by a sparse genotyping array or a genome build other than GRCh38 -- consider imputing your data to increase SNP coverage, then re-upload.".
- user12 job 2 (should be rejected), page shows: "Only 400 of 229986 Diet Network reference SNPs were found in your data (minimum 1000 required for reliable predictions). This is often caused by a sparse genotyping array or a genome build other than GRCh38 -- consider imputing your data to increase SNP coverage, then re-upload.".

Browser console errors and failed requests:

- ×24: `Failed to load resource: the server responded with a status of 401 ()`
- ×2: `Failed to load resource: the server responded with a status of 429 ()`
- ×1: `Failed to load resource: the server responded with a status of 404 ()`
- ×1: `Failed to load resource: the server responded with a status of 409 ()`


## Usage statistics report on this run

```
=== Overview ===
 users_signed_up | users_verified | users_with_jobs | jobs_submitted | jobs_successful | jobs_failed | jobs_in_progress | samples_inferred 
-----------------+----------------+-----------------+----------------+-----------------+-------------+------------------+------------------
              12 |             12 |              12 |             18 |              16 |           2 |                0 |              800


=== Per user (users with at least one job) ===
  user   | jobs_submitted | jobs_successful | samples_inferred 
---------+----------------+-----------------+------------------
 user 1  |              1 |               1 |               50
 user 2  |              1 |               1 |               50
 user 3  |              2 |               2 |              100
 user 4  |              3 |               3 |              150
 user 5  |              1 |               1 |               50
 user 6  |              1 |               1 |               50
 user 7  |              2 |               2 |              100
 user 8  |              2 |               2 |              100
 user 9  |              1 |               1 |               50
 user 10 |              2 |               0 |                0
 user 11 |              1 |               1 |               50
 user 12 |              1 |               1 |               50


=== Positions per successful analysis (panel SNPs used) ===
 analyses | min_positions | median_positions | mean_positions | max_positions | panel_size 
----------+---------------+------------------+----------------+---------------+------------
       16 |        229986 |           229986 |         229986 |        229986 |     229986


=== Per month ===
  month  | active_users | jobs_submitted | jobs_successful | samples_inferred 
---------+--------------+----------------+-----------------+------------------
 2026-11 |           12 |             18 |              16 |              800
```

## All checks

- ✅ user1 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user1 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user1 job 2: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user1 job 2: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user1 job 3: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user1 job 3: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user2 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user2 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user3 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user3 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user4 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user4 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user4 job 2: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user4 job 2: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user5 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user5 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user6 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user6 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user7 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user7 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user8 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user8 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user8 job 2: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user8 job 2: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user9 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user9 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user10 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user10 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user11 job 1: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user11 job 1: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ user11 job 2: zip is AES-256, refuses a wrong password, has exactly its own 50 samples
- ✅ user11 job 2: zip has the 4 plots (PNG) and no infer.sh scratch
- ✅ Postgres: 12 users (expected 12)
- ✅ Postgres: 18 jobs (expected 18)
- ✅ user1: browser flow completed (plink, 3 job(s))
- ✅ user1: Postgres user verified, active, consented, 3 job(s)
- ✅ user1: every job ended done (['done', 'done', 'done'])
- ✅ user1: job timestamps created <= started <= completed
- ✅ user1: sample_count = 50 on every job
- ✅ user1: overlap recorded and reliable on every job
- ✅ user1: raw upload deleted after every success
- ✅ user1: each later job uploaded after the previous one finished
- ✅ user1: dashboard lists 3 job(s) (saw 3)
- ✅ user2: browser flow completed (plink, 1 job(s))
- ✅ user2: Postgres user verified, active, consented, 1 job(s)
- ✅ user2: every job ended done (['done'])
- ✅ user2: job timestamps created <= started <= completed
- ✅ user2: sample_count = 50 on every job
- ✅ user2: overlap recorded and reliable on every job
- ✅ user2: raw upload deleted after every success
- ✅ user2: each later job uploaded after the previous one finished
- ✅ user2: dashboard lists 1 job(s) (saw 1)
- ✅ user3: browser flow completed (plink, 1 job(s))
- ✅ user3: Postgres user verified, active, consented, 1 job(s)
- ✅ user3: every job ended done (['done'])
- ✅ user3: job timestamps created <= started <= completed
- ✅ user3: sample_count = 50 on every job
- ✅ user3: overlap recorded and reliable on every job
- ✅ user3: raw upload deleted after every success
- ✅ user3: each later job uploaded after the previous one finished
- ✅ user3: dashboard lists 1 job(s) (saw 1)
- ✅ user4: browser flow completed (plink, 2 job(s))
- ✅ user4: Postgres user verified, active, consented, 2 job(s)
- ✅ user4: every job ended done (['done', 'done'])
- ✅ user4: job timestamps created <= started <= completed
- ✅ user4: sample_count = 50 on every job
- ✅ user4: overlap recorded and reliable on every job
- ✅ user4: raw upload deleted after every success
- ✅ user4: each later job uploaded after the previous one finished
- ✅ user4: dashboard lists 2 job(s) (saw 2)
- ✅ user5: browser flow completed (plink, 1 job(s))
- ✅ user5: Postgres user verified, active, consented, 1 job(s)
- ✅ user5: every job ended done (['done'])
- ✅ user5: job timestamps created <= started <= completed
- ✅ user5: sample_count = 50 on every job
- ✅ user5: overlap recorded and reliable on every job
- ✅ user5: raw upload deleted after every success
- ✅ user5: each later job uploaded after the previous one finished
- ✅ user5: dashboard lists 1 job(s) (saw 1)
- ✅ user6: browser flow completed (plink, 1 job(s))
- ✅ user6: Postgres user verified, active, consented, 1 job(s)
- ✅ user6: every job ended done (['done'])
- ✅ user6: job timestamps created <= started <= completed
- ✅ user6: sample_count = 50 on every job
- ✅ user6: overlap recorded and reliable on every job
- ✅ user6: raw upload deleted after every success
- ✅ user6: each later job uploaded after the previous one finished
- ✅ user6: dashboard lists 1 job(s) (saw 1)
- ✅ user7: browser flow completed (plink, 1 job(s))
- ✅ user7: Postgres user verified, active, consented, 1 job(s)
- ✅ user7: every job ended done (['done'])
- ✅ user7: job timestamps created <= started <= completed
- ✅ user7: sample_count = 50 on every job
- ✅ user7: overlap recorded and reliable on every job
- ✅ user7: raw upload deleted after every success
- ✅ user7: each later job uploaded after the previous one finished
- ✅ user7: dashboard lists 1 job(s) (saw 1)
- ✅ user8: browser flow completed (vcf, 2 job(s))
- ✅ user8: Postgres user verified, active, consented, 2 job(s)
- ✅ user8: every job ended done (['done', 'done'])
- ✅ user8: job timestamps created <= started <= completed
- ✅ user8: sample_count = 50 on every job
- ✅ user8: overlap recorded and reliable on every job
- ✅ user8: raw upload deleted after every success
- ✅ user8: each later job uploaded after the previous one finished
- ✅ user8: dashboard lists 2 job(s) (saw 2)
- ✅ user9: browser flow completed (vcf.gz, 1 job(s))
- ✅ user9: Postgres user verified, active, consented, 1 job(s)
- ✅ user9: every job ended done (['done'])
- ✅ user9: job timestamps created <= started <= completed
- ✅ user9: sample_count = 50 on every job
- ✅ user9: overlap recorded and reliable on every job
- ✅ user9: raw upload deleted after every success
- ✅ user9: each later job uploaded after the previous one finished
- ✅ user9: dashboard lists 1 job(s) (saw 1)
- ✅ user10: browser flow completed (bgen, 1 job(s))
- ✅ user10: Postgres user verified, active, consented, 1 job(s)
- ✅ user10: every job ended done (['done'])
- ✅ user10: job timestamps created <= started <= completed
- ✅ user10: sample_count = 50 on every job
- ✅ user10: overlap recorded and reliable on every job
- ✅ user10: raw upload deleted after every success
- ✅ user10: each later job uploaded after the previous one finished
- ✅ user10: dashboard lists 1 job(s) (saw 1)
- ✅ user11: browser flow completed (bgen, 2 job(s))
- ✅ user11: Postgres user verified, active, consented, 2 job(s)
- ✅ user11: every job ended done (['done', 'done'])
- ✅ user11: job timestamps created <= started <= completed
- ✅ user11: sample_count = 50 on every job
- ✅ user11: overlap recorded and reliable on every job
- ✅ user11: raw upload deleted after every success
- ✅ user11: each later job uploaded after the previous one finished
- ✅ user11: dashboard lists 2 job(s) (saw 2)
- ✅ user12: browser flow completed (low_overlap, 2 job(s))
- ✅ user12: Postgres user verified, active, consented, 2 job(s)
- ✅ user12: every job ended failed (['failed', 'failed'])
- ✅ user12: job timestamps created <= started <= completed
- ✅ user12: error message stored on every failed job
- ✅ user12: each later job uploaded after the previous one finished
- ✅ user12: dashboard lists 2 job(s) (saw 2)
- ✅ user1: emails = 1 verification + 3 started + 3 'results are ready' (got 1 + 3 + 3, 7 total)
- ✅ user1: homepage box mentions PLINK
- ✅ user2: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user2: homepage box mentions PLINK
- ✅ user3: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user3: homepage box mentions PLINK
- ✅ user4: emails = 1 verification + 2 started + 2 'results are ready' (got 1 + 2 + 2, 5 total)
- ✅ user4: homepage box mentions PLINK
- ✅ user5: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user5: homepage box mentions PLINK
- ✅ user6: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user6: homepage box mentions PLINK
- ✅ user7: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user7: homepage box mentions PLINK
- ✅ user8: emails = 1 verification + 2 started + 2 'results are ready' (got 1 + 2 + 2, 5 total)
- ✅ user8: homepage box mentions PLINK
- ✅ user9: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user9: homepage box mentions PLINK
- ✅ user10: emails = 1 verification + 1 started + 1 'results are ready' (got 1 + 1 + 1, 3 total)
- ✅ user10: homepage box mentions PLINK
- ✅ user11: emails = 1 verification + 2 started + 2 'results are ready' (got 1 + 2 + 2, 5 total)
- ✅ user11: homepage box mentions PLINK
- ✅ user12: emails = 1 verification + 2 started + 2 'job failed' (got 1 + 2 + 2, 5 total)
- ✅ user12: homepage box mentions PLINK
- ✅ MailHog: no emails to unknown recipients ([])
- ✅ FCFS: no job started ahead of one uploaded over 1 s earlier (0 found: [])
- ✅ concurrency cap: at most 9 jobs ran at once (peak 9)
- ✅ queue exercised: 3 job(s) waited > 5 s for a slot
- ✅ queued jobs start within 10 s of a slot freeing ([('user8#1', 0.0), ('user11#1', 0.0), ('user12#2', 0.1)])
- ✅ every successful job downloaded (16/16)
- ✅ selecting or dropping .bed/.bim/.fam together submits (4/4 users)
- ✅ user1: another user's job is refused (404)
- ✅ user5: submitting .bed alone shows a message on the page
- ✅ user7: second upload while a job is active is refused (409)
- ✅ user12 job 1: rejection message reports the low overlap
- ✅ user12 job 2: rejection message reports the low overlap
- ✅ usage report: overview table found
- ✅ usage report: 12 users (expected 12)
- ✅ usage report: 18 jobs (expected 18)
- ✅ usage report: 16 successful (expected 16)
- ✅ usage report: 800 samples inferred (expected 800)
