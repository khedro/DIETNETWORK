#!/usr/bin/env python3
"""Turns one simulation run's outputs into report.md and prints it: per-user
timings, queue order and concurrency, API latency, resource peaks, emails, and
the contents of every downloaded zip.

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
jobs = {j["email"].split("@")[0]: j for j in json.load(open(os.path.join(out_dir, "jobs.json")))}
emails = json.load(open(os.path.join(out_dir, "emails.json")))
users = results["users"]
# SIM_USERS may have run only some of the users.
expected = {n: cfg for n, cfg in expected.items() if n in users}

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

# --- Zips: right password opens, wrong one doesn't, table holds exactly this user's samples
zip_results: dict[str, dict] = {}
for name, cfg in expected.items():
    if cfg["outcome"] != "done":
        continue
    path = os.path.join(out_dir, "zips", f"{name}.zip")
    info: dict = {"present": os.path.exists(path)}
    zip_results[name] = info
    if not info["present"]:
        continue
    try:
        with pyzipper.AESZipFile(path) as zf:
            members = zf.infolist()
            info["all_aes"] = all(m.flag_bits & 0x1 and getattr(m, "wz_aes_strength", None) == 3 for m in members)
            zf.setpassword(b"definitely-wrong")
            try:
                zf.read("result_job_log.txt")
                info["wrong_password_rejected"] = False
            except RuntimeError:
                info["wrong_password_rejected"] = True
            zf.setpassword(results["zipPassword"].encode())
            rows = list(csv.DictReader(io.StringIO(zf.read("result_results_table.tsv").decode()), delimiter="\t"))
            log_text = zf.read("result_job_log.txt").decode()
            info["npz"] = len([n for n in zf.namelist() if n.endswith(".npz")])
    except Exception as exc:  # noqa: BLE001 -- reported as a failed check
        info["error"] = str(exc)
        continue
    wanted = set(cfg["samples"])
    got = [r["Sample"] for r in rows]
    # A format may report FID_IID; match on the IID.
    matched = {s for s in wanted if any(g == s or g.endswith("_" + s) for g in got)}
    info["rows"] = len(rows)
    info["own_samples"] = len(matched)
    info["foreign_rows"] = sum(1 for g in got if not any(g == s or g.endswith("_" + s) for s in wanted))
    info["consensus_continent"] = sum(r["Continent consensus"] != "NA" for r in rows)
    info["consensus_population"] = sum(r["Population consensus"] != "NA" for r in rows)
    m = re.search(r"Overlap by position:\s*(\d+)", log_text)
    info["overlap_by_position"] = int(m.group(1)) if m else None
    check(
        info["all_aes"] and info["wrong_password_rejected"] and info["rows"] == 50
        and info["own_samples"] == 50 and info["foreign_rows"] == 0 and info["npz"] == 15,
        f"{name}: zip is AES-256, refuses a wrong password, has exactly its own 50 samples and 15 model files",
    )

# --- Per-user outcome checks
for name, cfg in expected.items():
    rec = users.get(name, {})
    job = jobs.get(name)
    check(rec.get("ok") and not rec.get("fatal"), f"{name}: browser flow completed ({cfg['format']})")
    check(job is not None and job["status"] == cfg["outcome"], f"{name}: job ended {cfg['outcome']}")
    if cfg["outcome"] == "done" and job:
        check(job["sample_count"] == 50, f"{name}: sample_count = 50 in the database")
        check(job["raw_exists"] is False, f"{name}: raw upload deleted after success")
    subjects = emails.get(name, [])
    wanted = ["verify your email", "has started", "results are ready" if cfg["outcome"] == "done" else "job failed"]
    check(all(any(w_ in s for s in subjects) for w_ in wanted), f"{name}: received verification, started and final emails")
    check(rec.get("homeMentionsPlink"), f"{name}: homepage box mentions PLINK")

# --- Queue timeline
timed = [(n, jobs[n]) for n in names if n in jobs and jobs[n]["started_at"]]
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
check(not inversions, f"FCFS: no job started ahead of one uploaded over 1 s earlier ({len(inversions)} found)")
check(peak <= 9, f"concurrency cap: at most 9 jobs ran at once (peak {peak})")

# --- Report
ok_count = sum(1 for ok, _ in checks if ok)
w("# 12-user browser simulation report")
w("")
w(f"Total time {results['totalSeconds']:.0f} s. Checks: **{ok_count}/{len(checks)} passed**.")
w("")
w("## Users")
w("")
w("| User | Format | Upload MB | Sign-up to logged in (s) | Upload (s) | Queue wait (s) | Job run (s) | Download (s) | Attempts | Outcome |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
for name in names:
    rec, job, cfg = users.get(name, {}), jobs.get(name), expected[name]
    signup = sum(step_seconds(rec, s) or 0 for s in ("signup", "email-arrives", "verify", "login")) if rec else None
    wait = run = None
    if job and job["started_at"]:
        wait = (ts(job["started_at"]) - ts(job["created_at"])).total_seconds()
        run = (ts(job["completed_at"]) - ts(job["started_at"])).total_seconds() if job["completed_at"] else None
    attempts = rec.get("downloadAttempts") or []
    ok_dl = [a for a in attempts if a["status"] == 200]
    outcome = job["status"] if job else "no job"
    w(f"| {name} | {cfg['format']} | {cfg['bytes'] / 1e6:.1f} | {fmt(signup)} | {fmt(step_seconds(rec, 'upload'))} | {fmt(wait)} | {fmt(run)} | {fmt(ok_dl[0]['seconds'] if ok_dl else None)} | {len(attempts) or '-'} | {outcome} |")
w("")

done_runs = [(ts(j["completed_at"]) - ts(j["started_at"])).total_seconds() for n, j in timed if j["status"] == "done"]
waits = [(ts(j["started_at"]) - ts(j["created_at"])).total_seconds() for n, j in timed]
w("## Queue and concurrency")
w("")
if done_runs:
    w(f"- Job run time: median {statistics.median(done_runs):.0f} s, min {min(done_runs):.0f} s, max {max(done_runs):.0f} s.")
w(f"- Queue wait: median {statistics.median(waits):.1f} s, max {max(waits):.1f} s." if waits else "- No job started.")
w(f"- Peak jobs running at once (from database timestamps): **{peak}** (limit 9).")
seen = {n: sorted(set(users[n]["queuePositionsSeen"])) for n in names if users.get(n, {}).get("queuePositionsSeen")}
w(f"- Queue positions shown on job pages: {seen if seen else 'none seen'}.")
w(f"- Upload order: {', '.join(by_created)}.")
w(f"- Start order: {', '.join(by_started)}.")
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
w("## Simultaneous downloads")
w("")
all_attempts = [a for rec in users.values() for a in rec.get("downloadAttempts", [])]
refused = sum(a["status"] == 429 for a in all_attempts)
ok_dl = [a["seconds"] for a in all_attempts if a["status"] == 200]
w(f"- {len(ok_dl)} succeeded; {refused} attempt(s) refused with 429 (the 9-at-once limit) and retried.")
if ok_dl:
    w(f"- Successful download time: median {statistics.median(ok_dl):.1f} s, max {max(ok_dl):.1f} s.")
sizes = [rec["zipBytes"] for rec in users.values() if rec.get("zipBytes")]
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
    w(f"- {name} (should be rejected), page shows: \"{users.get(name, {}).get('errorMessage')}\".")
    check("400" in (users.get(name, {}).get("errorMessage") or ""), f"{name}: rejection message reports the low overlap")
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
done = sum(1 for n in names if expected[n]["outcome"] == "done")
m = re.search(r"=== Overview ===\n.*\n.*\n(.*)\n", usage)
if m:
    cells = [c.strip() for c in m.group(1).split("|")]
    check(cells[0] == str(len(names)), f"usage report: {cells[0]} users (expected {len(names)})")
    check(cells[3] == str(len(names)), f"usage report: {cells[3]} jobs (expected {len(names)})")
    check(cells[4] == str(done), f"usage report: {cells[4]} successful (expected {done})")
    check(cells[7] == str(done * 50), f"usage report: {cells[7]} samples inferred (expected {done * 50})")
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
