#!/usr/bin/env python3
"""Turns one simulation run's outputs into report.md and prints it: per-job
timings, queue order and concurrency, the users and jobs in Postgres, the
emails MailHog caught, API latency, resource peaks, and the contents of every
downloaded zip. Some users submit several jobs in a row (simulate.cjs
JOBS_PER_USER), so everything job-related is checked per job.

Runs inside the backend image (needs pyzipper). See run.sh.

Usage: analyze.py DATA_DIR OUT_DIR
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime

import pyzipper

data_dir, out_dir = sys.argv[1:3]
expected = json.load(open(os.path.join(data_dir, "expected.json")))
results = json.load(open(os.path.join(out_dir, "results.json")))
db_jobs = json.load(open(os.path.join(out_dir, "jobs.json")))
db_users = {u["email"].split("@")[0]: u for u in json.load(open(os.path.join(out_dir, "users.json")))}
emails = json.load(open(os.path.join(out_dir, "emails.json")))
users = results["users"]
# SIM_USERS may have run only some of the users.
expected = {n: cfg for n, cfg in expected.items() if n in users}
planned = {n: users[n].get("jobsPlanned", 1) for n in expected}

# Jobs per user, in upload order; job k of a user is jobs_by_user[name][k - 1].
jobs_by_user: dict[str, list[dict]] = defaultdict(list)
for j in sorted(db_jobs, key=lambda j: j["created_at"]):
    jobs_by_user[j["email"].split("@")[0]].append(j)

PLOTS = [
    "result_barplot_population.png",
    "result_barplot_continent.png",
    "result_representation_pop.png",
    "result_representation_continent.png",
]

checks: list[tuple[bool, str]] = []
lines: list[str] = []
w = lines.append


def check(ok: bool, text: str) -> None:
    checks.append((bool(ok), text))


def ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def step_seconds(rec: dict, label: str) -> float | None:
    for s in rec["steps"]:
        if s["label"] == label:
            return s["seconds"]
    return None


def fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


names = list(expected)
total_jobs = sum(planned.values())
done_jobs = sum(planned[n] for n in names if expected[n]["outcome"] == "done")

# --- Zips: right password opens, wrong one doesn't, table holds exactly this user's samples
for name, cfg in expected.items():
    if cfg["outcome"] != "done":
        continue
    for k in range(1, planned[name] + 1):
        label = f"{name} job {k}"
        path = os.path.join(out_dir, "zips", f"{name}-job{k}.zip")
        if not os.path.exists(path):
            check(False, f"{label}: zip downloaded")
            continue
        try:
            with pyzipper.AESZipFile(path) as zf:
                members = zf.infolist()
                all_aes = all(m.flag_bits & 0x1 and getattr(m, "wz_aes_strength", None) == 3 for m in members)
                zf.setpassword(b"definitely-wrong")
                try:
                    zf.read("result_job_log.txt")
                    wrong_rejected = False
                except RuntimeError:
                    wrong_rejected = True
                zf.setpassword(results["zipPassword"].encode())
                names_in_zip = set(zf.namelist())
                rows = list(csv.DictReader(io.StringIO(zf.read("result_results_table.tsv").decode()), delimiter="\t"))
                plots_ok = all(p in names_in_zip and zf.read(p)[:8] == b"\x89PNG\r\n\x1a\n" for p in PLOTS)
        except Exception as exc:  # noqa: BLE001 -- reported as a failed check
            check(False, f"{label}: zip opens ({exc})")
            continue
        wanted = set(cfg["samples"])
        got = [r["Sample"] for r in rows]
        # A format may report FID_IID; match on the IID.
        own = {s for s in wanted if any(g == s or g.endswith("_" + s) for g in got)}
        foreign = sum(1 for g in got if not any(g == s or g.endswith("_" + s) for s in wanted))
        scratch = [n for n in names_in_zip if "/" in n or n.endswith((".npz", ".hdf5", ".bed", ".bim", ".fam"))]
        check(
            all_aes and wrong_rejected and len(rows) == 50 and len(own) == 50 and foreign == 0,
            f"{label}: zip is AES-256, refuses a wrong password, has exactly its own 50 samples",
        )
        check(plots_ok and not scratch, f"{label}: zip has the 4 plots (PNG) and no infer.sh scratch")

# --- Postgres: users and jobs
check(len(db_users) == len(names), f"Postgres: {len(db_users)} users (expected {len(names)})")
check(len(db_jobs) == total_jobs, f"Postgres: {len(db_jobs)} jobs (expected {total_jobs})")
for name, cfg in expected.items():
    rec = users.get(name, {})
    u = db_users.get(name)
    js = jobs_by_user.get(name, [])
    check(rec.get("ok") and not rec.get("fatal"), f"{name}: browser flow completed ({cfg['format']}, {planned[name]} job(s))")
    check(
        u is not None and u["is_verified"] and u["is_active"] and u["consented"] and u["job_count"] == planned[name],
        f"{name}: Postgres user verified, active, consented, {planned[name]} job(s)",
    )
    check(
        len(js) == planned[name] and all(j["status"] == cfg["outcome"] for j in js),
        f"{name}: every job ended {cfg['outcome']} ({[j['status'] for j in js]})",
    )
    check(
        all(j["started_at"] and j["completed_at"] and ts(j["created_at"]) <= ts(j["started_at"]) <= ts(j["completed_at"]) for j in js),
        f"{name}: job timestamps created <= started <= completed",
    )
    if cfg["outcome"] == "done":
        check(all(j["sample_count"] == 50 for j in js), f"{name}: sample_count = 50 on every job")
        check(all(j["snp_overlap_count"] and j["is_reliable"] for j in js), f"{name}: overlap recorded and reliable on every job")
        check(all(j["raw_exists"] is False and j["raw_deleted_at"] for j in js), f"{name}: raw upload deleted after every success")
    else:
        check(all(j["error_message"] for j in js), f"{name}: error message stored on every failed job")
    # Each job after the first was uploaded only once the previous one had finished.
    check(
        all(ts(b["created_at"]) >= ts(a["completed_at"]) for a, b in zip(js, js[1:])),
        f"{name}: each later job uploaded after the previous one finished",
    )
    check(rec.get("dashboardRows") == planned[name], f"{name}: dashboard lists {planned[name]} job(s) (saw {rec.get('dashboardRows')})")

# --- MailHog: one verification email, then a started and a final email per job
for name, cfg in expected.items():
    subjects = emails.get(name, [])
    n_verify = sum("verify your email" in s for s in subjects)
    n_started = sum("has started" in s for s in subjects)
    final = "results are ready" if cfg["outcome"] == "done" else "job failed"
    n_final = sum(final in s for s in subjects)
    check(
        n_verify == 1 and n_started == planned[name] and n_final == planned[name] and len(subjects) == 1 + 2 * planned[name],
        f"{name}: emails = 1 verification + {planned[name]} started + {planned[name]} '{final}' "
        f"(got {n_verify} + {n_started} + {n_final}, {len(subjects)} total)",
    )
    check(users.get(name, {}).get("homeMentionsPlink"), f"{name}: homepage box mentions PLINK")
stray = sorted(set(emails) - set(names))
check(not stray, f"MailHog: no emails to unknown recipients ({stray})")

# --- Queue timeline over every job
timed = [(f"{n}#{k + 1}", j) for n in names for k, j in enumerate(jobs_by_user.get(n, [])) if j["started_at"]]
timeline = sorted(timed, key=lambda kv: ts(kv[1]["started_at"]))
by_created = [n for n, _ in sorted(timed, key=lambda kv: ts(kv[1]["created_at"]))]
by_started = [n for n, _ in timeline]
events = []
for _, j in timed:
    events.append((ts(j["started_at"]), 1))
    events.append((ts(j["completed_at"]), -1))
peak = current = 0
for _, delta in sorted(events, key=lambda e: (e[0], e[1])):
    current += delta
    peak = max(peak, current)
# FCFS: any job started before one created over a second earlier was queue-jumping.
# Closer than that, created_at order and queue order can legitimately differ.
inversions = []
for i, (a, ja) in enumerate(timed):
    for b, jb in timed[i + 1 :]:
        ca, cb = ts(ja["created_at"]), ts(jb["created_at"])
        sa, sb = ts(ja["started_at"]), ts(jb["started_at"])
        if (ca - cb).total_seconds() > 1 and sa < sb:
            inversions.append(f"{a} before {b}")
        elif (cb - ca).total_seconds() > 1 and sb < sa:
            inversions.append(f"{b} before {a}")
queued = [(n, (ts(j["started_at"]) - ts(j["created_at"])).total_seconds()) for n, j in timed]
queued = [(n, s) for n, s in queued if s > 5]
check(not inversions, f"FCFS: no job started ahead of one uploaded over 1 s earlier ({len(inversions)} found: {inversions[:5]})")
check(peak <= 9, f"concurrency cap: at most 9 jobs ran at once (peak {peak})")
check(len(queued) >= 3, f"queue exercised: {len(queued)} job(s) waited > 5 s for a slot")
# A queued job must start right when a slot frees up, not minutes later.
lags = []
for n, j in timed:
    start = ts(j["started_at"])
    if (start - ts(j["created_at"])).total_seconds() <= 5:
        continue
    freed = [ts(o["completed_at"]) for _, o in timed if o["completed_at"] and ts(o["completed_at"]) <= start]
    if freed:
        lags.append((n, (start - max(freed)).total_seconds()))
check(all(lag <= 10 for _, lag in lags), f"queued jobs start within 10 s of a slot freeing ({[(n, round(l, 1)) for n, l in lags]})")

# --- Report
ok_count = sum(1 for ok, _ in checks if ok)
w("# 12-user browser simulation report")
w("")
w(f"Total time {results['totalSeconds']:.0f} s. Checks: **{ok_count}/{len(checks)} passed**.")
w("")
w(f"{len(names)} users, {total_jobs} jobs (repeat submissions: "
  f"{', '.join(f'{n} x{planned[n]}' for n in names if planned[n] > 1) or 'none'}).")
w("")
w("## Jobs")
w("")
w("| Job | Format | Upload MB | Uploaded at (s) | Queue wait (s) | Job run (s) | Download (s) | Attempts | Outcome |")
w("|---|---|---:|---:|---:|---:|---:|---:|---|")
for name in names:
    rec, cfg = users.get(name, {}), expected[name]
    sims = rec.get("jobs") or []
    for k, job in enumerate(jobs_by_user.get(name, []), start=1):
        sim = sims[k - 1] if k <= len(sims) else {}
        wait = run = None
        if job["started_at"]:
            wait = (ts(job["started_at"]) - ts(job["created_at"])).total_seconds()
            run = (ts(job["completed_at"]) - ts(job["started_at"])).total_seconds() if job["completed_at"] else None
        attempts = sim.get("downloadAttempts") or []
        ok_dl = [a for a in attempts if a["status"] == 200]
        w(f"| {name}#{k} | {cfg['format']} | {cfg['bytes'] / 1e6:.1f} | {fmt(sim.get('uploadDoneS'))} | {fmt(wait)} | "
          f"{fmt(run)} | {fmt(ok_dl[0]['seconds'] if ok_dl else None)} | {len(attempts) or '-'} | {job['status']} |")
w("")

done_runs = [(ts(j["completed_at"]) - ts(j["started_at"])).total_seconds() for n, j in timed if j["status"] == "done"]
waits = [(ts(j["started_at"]) - ts(j["created_at"])).total_seconds() for n, j in timed]
w("## Queue and concurrency")
w("")
if done_runs:
    w(f"- Job run time: median {statistics.median(done_runs):.0f} s, min {min(done_runs):.0f} s, max {max(done_runs):.0f} s.")
w(f"- Queue wait: median {statistics.median(waits):.1f} s, max {max(waits):.1f} s." if waits else "- No job started.")
w(f"- Jobs that waited for a slot (> 5 s): {', '.join(f'{n} ({s:.0f} s)' for n, s in queued) or 'none'}.")
w(f"- Delay from a slot freeing to the next queued job starting: {', '.join(f'{n} {l:.1f} s' for n, l in lags) or '-'}.")
w(f"- Peak jobs running at once (from database timestamps): **{peak}** (limit 9).")
seen = {n: sorted(set(users[n]["queuePositionsSeen"])) for n in names if users.get(n, {}).get("queuePositionsSeen")}
w(f"- Queue positions shown on job pages: {seen if seen else 'none seen'}.")
w(f"- Upload order: {', '.join(by_created)}.")
w(f"- Start order: {', '.join(by_started)}.")
w("")

w("## Postgres")
w("")
w("| User | Verified | Active | Consented | Jobs in DB | Statuses | Raw deleted |")
w("|---|---|---|---|---:|---|---|")
for name in names:
    u = db_users.get(name) or {}
    js = jobs_by_user.get(name, [])
    raw = ", ".join("yes" if not j["raw_exists"] else "no" for j in js)
    w(f"| {name} | {u.get('is_verified')} | {u.get('is_active')} | {u.get('consented')} | {u.get('job_count')} | "
      f"{', '.join(j['status'] for j in js)} | {raw} |")
w("")

w("## Emails caught by MailHog")
w("")
w("| User | Count | Subjects |")
w("|---|---:|---|")
for name in names:
    subjects = emails.get(name, [])
    counted = defaultdict(int)
    for s in subjects:
        counted[re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "{id}", s)] += 1
    w(f"| {name} | {len(subjects)} | {'; '.join(f'{s} ×{c}' if c > 1 else s for s, c in counted.items())} |")
w("")

# --- API latency
calls = defaultdict(list)
statuses = defaultdict(int)
for rec in users.values():
    for c in rec["apiCalls"]:
        key = f"{c['method']} {c['path']}"
        statuses[(key, c["status"])] += 1
        if c["ms"] is not None and c["ms"] >= 0:
            calls[key].append(c["ms"])
w("## API response times (from the browsers)")
w("")
w("| Endpoint | Calls | Median ms | p95 ms | Max ms |")
w("|---|---:|---:|---:|---:|")
for key, values in sorted(calls.items()):
    w(f"| `{key}` | {len(values)} | {statistics.median(values):.0f} | {pct(values, 0.95):.0f} | {max(values):.0f} |")
w("")
non_ok = {k: v for k, v in statuses.items() if k[1] >= 400}
w("Responses with an error status:")
w("")
if non_ok:
    for (key, status), count in sorted(non_ok.items()):
        w(f"- `{key}` → {status}: {count}")
else:
    w("- none")
w("")

# --- Resources
samples = list(csv.DictReader(open(os.path.join(out_dir, "metrics.csv"))))


def mem_mb(usage: str) -> float:
    m = re.match(r"([\d.]+)(\w+)", usage.split("/")[0].strip())
    value, unit = float(m.group(1)), m.group(2)
    return value * {"B": 1e-6, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "TiB": 1024**2}.get(unit, 1)


w("## Resources (sampled by `docker stats`)")
w("")
w("| Container | Peak CPU (% of one core) | Peak memory (MB) |")
w("|---|---:|---:|")
by_container = defaultdict(list)
for s in samples:
    by_container[s["container"]].append(s)
for container, rows in sorted(by_container.items()):
    peak_cpu = max(float(r["cpu_pct"].rstrip("%") or 0) for r in rows)
    peak_mem = max(mem_mb(r["mem_usage"]) for r in rows)
    w(f"| {container} | {peak_cpu:.0f} | {peak_mem:.0f} |")
w("")
if samples:
    w(f"- Host load (1 min) peak: {max(float(s['load1']) for s in samples):.1f} on 128 cores.")
    w(f"- Most model processes (`inference.py`) running at once: {max(int(s['inference_procs']) for s in samples)}.")
    w(f"- Most jobs inside `infer.sh` at once: {max(int(s['infer_sh_procs']) for s in samples)}.")
    w(f"- `/data` peak size: {max(int(s['data_mb'] or 0) for s in samples)} MB.")
w("")


# --- Downloads
w("## Downloads")
w("")
all_attempts = [a for rec in users.values() for job in rec.get("jobs", []) for a in job.get("downloadAttempts", [])]
refused = sum(a["status"] == 429 for a in all_attempts)
ok_dl = [a["seconds"] for a in all_attempts if a["status"] == 200]
w(f"- {len(ok_dl)} succeeded (expected {done_jobs}); {refused} attempt(s) refused with 429 (the 9-at-once limit) and retried.")
check(len(ok_dl) == done_jobs, f"every successful job downloaded ({len(ok_dl)}/{done_jobs})")
if ok_dl:
    w(f"- Successful download time: median {statistics.median(ok_dl):.1f} s, max {max(ok_dl):.1f} s.")
sizes = [job["zipBytes"] for rec in users.values() for job in rec.get("jobs", []) if job.get("zipBytes")]
if sizes:
    w(f"- Zip size: median {statistics.median(sizes) / 1e6:.1f} MB.")
w("")

# --- Deliberate probes and findings
w("## Findings from the browser")
w("")
blocked = [n for n in names if any(f["kind"] == "plink-together-blocked" for f in users.get(n, {}).get("findings", []))]
together = [n for n in names if expected[n]["selection"] in ("together", "dropped")]
if together:
    check(not blocked, f"selecting or dropping .bed/.bim/.fam together submits ({len(together) - len(blocked)}/{len(together)} users)")
if blocked:
    w(f"- **Upload form bug:** selecting the three PLINK files together did not submit for {', '.join(blocked)}. They had to pick `.bim` and `.fam` a second time.")
elif together:
    w(f"- Selecting or dropping the three PLINK files together submitted for all {len(together)} users ({', '.join(together)}).")
for name in names:
    for f in users.get(name, {}).get("findings", []):
        if f["kind"] == "bed-only":
            check(bool(f["banner"]), f"{name}: submitting .bed alone shows a message on the page")
            w(f"- {name}, submitting a `.bed` without `.bim`/`.fam`: page shows: \"{f['banner']}\".")
        if f["kind"] == "second-upload":
            check(f["status"] == 409, f"{name}: second upload while a job is active is refused (409)")
            w(f"- {name}, second upload while a job is active: {f['status']}, page shows: \"{f['banner']}\".")
        if f["kind"] == "other-users-job":
            check(f["status"] == 404, f"{name}: another user's job is refused (404)")
            w(f"- {name} opening another user's job: {f['status']}, page shows: \"{f['banner']}\".")
rejected = [n for n in names if expected[n]["outcome"] == "failed"]
for name in rejected:
    for job in users.get(name, {}).get("jobs", []):
        w(f"- {name} job {job['k']} (should be rejected), page shows: \"{job.get('errorMessage')}\".")
        check("400" in (job.get("errorMessage") or ""), f"{name} job {job['k']}: rejection message reports the low overlap")
problems = {
    n: {k: users[n][k] for k in ("consoleErrors", "pageErrors", "failedRequests") if users[n].get(k)}
    for n in names if n in users
}
problems = {n: p for n, p in problems.items() if p}
unexpected_console = []
for n, p in problems.items():
    for text in p.get("consoleErrors", []) + p.get("pageErrors", []):
        unexpected_console.append(f"{n}: {text}")
    for f in p.get("failedRequests", []):
        unexpected_console.append(f"{n}: request failed {f['url']} {f['failure']}")
w("")
w("Browser console errors and failed requests:")
w("")
if unexpected_console:
    counted = defaultdict(int)
    for item in unexpected_console:
        counted[re.sub(r"^user\d+: ", "", item)[:200]] += 1
    for text, count in sorted(counted.items(), key=lambda kv: -kv[1]):
        w(f"- ×{count}: `{text}`")
else:
    w("- none")
w("")
for name in names:
    if users.get(name, {}).get("fatal"):
        w(f"- **{name} stopped:** {users[name]['fatal']}")
w("")

# --- Usage statistics
usage = open(os.path.join(out_dir, "usage_stats.txt")).read()
m = re.search(r"=== Overview ===\n.*\n.*\n(.*)\n", usage)
check(bool(m), "usage report: overview table found")
if m:
    cells = [c.strip() for c in m.group(1).split("|")]
    check(cells[0] == str(len(names)), f"usage report: {cells[0]} users (expected {len(names)})")
    check(cells[3] == str(total_jobs), f"usage report: {cells[3]} jobs (expected {total_jobs})")
    check(cells[4] == str(done_jobs), f"usage report: {cells[4]} successful (expected {done_jobs})")
    check(cells[7] == str(done_jobs * 50), f"usage report: {cells[7]} samples inferred (expected {done_jobs * 50})")
w("## Usage statistics report on this run")
w("")
w("```")
w(usage.strip())
w("```")
w("")

w("## All checks")
w("")
for ok, text in checks:
    w(f"- {'✅' if ok else '❌'} {text}")
w("")

# Header counted before the later checks were added; rewrite it with the final totals.
ok_count = sum(1 for ok, _ in checks if ok)
lines[2] = f"Total time {results['totalSeconds']:.0f} s. Checks: **{ok_count}/{len(checks)} passed**."
text = "\n".join(lines)
with open(os.path.join(out_dir, "report.md"), "w") as f:
    f.write(text)
print(text)
sys.exit(0 if ok_count == len(checks) else 1)
