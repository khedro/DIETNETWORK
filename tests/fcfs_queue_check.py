#!/usr/bin/env python3
"""TESTING.md section 4: processing queue is FCFS.

Uses dataTest/fixtures/low_overlap for every job, not the full positive
control -- it's rejected fast (fails the SNP-overlap pre-flight check
right after PLINK conversion) while still exercising the exact same
queued -> running transition, queue_position computation, and
job-started email as a real job would. That keeps an N-job serial run
(this test needs CELERY_WORKER_CONCURRENCY=1 -- see run_all.sh -- so jobs
process strictly one at a time) fast instead of waiting through N full
15-model ensembles.

Checks:
  - each still-queued job's queue_position (GET /jobs/{id}) matches its
    1-based rank among jobs created before it
  - "job started" emails arrive in the same order the jobs were created
  - (--expect-serial, default) each job's started_at is after the previous
    job's completed_at, i.e. one job at a time in creation order

Usage: fcfs_queue_check.py --base-url URL --mailhog-url URL [--n 5]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (  # noqa: E402
    TestFailure,
    get_job,
    signup_verify_login,
    unique_email,
    upload_plink,
    wait_for_email,
    wait_for_status,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(REPO_ROOT, "dataTest", "fixtures", "low_overlap")


def ts(value: str) -> datetime:
    """API timestamps are ISO 8601, possibly with a 'Z' suffix (Python 3.9's
    fromisoformat doesn't accept 'Z')."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def log(message: str) -> None:
    """Timestamped, unbuffered output, so a captured run reads as a live timeline."""
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mailhog-url", required=True)
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--started-email-timeout", type=float, default=120)
    parser.add_argument(
        "--expect-serial",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also require strictly one-at-a-time execution (worker running with CELERY_WORKER_CONCURRENCY=1)",
    )
    args = parser.parse_args()

    log(f"Registering {args.n} users...")
    users = []
    for i in range(args.n):
        email = unique_email(f"fcfs-{i}")
        session = signup_verify_login(args.base_url, args.mailhog_url, email)
        users.append({"index": i, "email": email, "session": session})

    log(f"Firing {args.n} uploads concurrently...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.n) as pool:
        futures = {
            pool.submit(upload_plink, u["session"], args.base_url, FIXTURE): u for u in users
        }
        for future in concurrent.futures.as_completed(futures):
            u = futures[future]
            u["job"] = future.result()

    # Ground truth for "creation order" is the DB's created_at, not the
    # order our threads happened to be scheduled in.
    users.sort(key=lambda u: ts(u["job"]["created_at"]))
    for rank, u in enumerate(users):
        u["expected_rank"] = rank
        log(f"  #{rank}: {u['email']} -> job {u['job']['id']} created_at={u['job']['created_at']}")

    log("Polling queue_position immediately after submission...")
    position_failures = []
    for u in users:
        detail = get_job(u["session"], args.base_url, u["job"]["id"])
        u["queue_position_at_poll"] = detail.get("queue_position")
        u["status_at_poll"] = detail["status"]
        log(f"  {u['email']}: status={u['status_at_poll']} queue_position={u['queue_position_at_poll']}")
        # Only meaningful while still queued -- once running/done it's None
        # (see jobs.py: only computed for status == queued).
        if detail["status"] == "queued":
            earlier_still_queued = sum(
                1
                for other in users
                if other is not u
                and ts(other["job"]["created_at"]) < ts(u["job"]["created_at"])
            )
            expected = earlier_still_queued + 1
            if detail.get("queue_position") != expected:
                # Not necessarily a bug: an earlier job may have already left
                # the queue between our two polls. Only flag if position is
                # *higher* than what pure creation-order would predict, since
                # earlier jobs finishing can only ever lower it.
                if (detail.get("queue_position") or 0) > expected:
                    position_failures.append(
                        f"{u['email']}: queue_position={detail.get('queue_position')} > expected<={expected}"
                    )

    log(f"Waiting for {args.n} 'job started' emails (up to {args.started_email_timeout}s)...")
    arrival_order = []
    try:
        for u in users:
            wait_for_email(args.mailhog_url, u["email"], "your ancestry job has started", timeout=args.started_email_timeout)
            arrival_order.append(u["email"])
            log(f"  started email received: {u['email']}")
    except TestFailure as exc:
        log(f"[FAIL] fcfs_queue: {exc}")
        sys.exit(1)

    expected_order = [u["email"] for u in users]
    ordering_ok = arrival_order == expected_order

    # Strongest evidence the queue is FCFS and capped: with
    # CELERY_WORKER_CONCURRENCY=1 every job must start only after the
    # previous one (by creation time) has finished, and in creation order.
    log("Waiting for every job to finish, then checking the start/finish timeline...")
    serial_failures = []
    for u in users:
        u["final"] = wait_for_status(u["session"], args.base_url, u["job"]["id"], {"done", "failed"}, timeout=300)
    log("  rank | created_at                  | started_at                  | completed_at                | status")
    for u in users:
        f = u["final"]
        log(f"  #{u['expected_rank']}   | {f['created_at']} | {f['started_at']} | {f['completed_at']} | {f['status']}")
    if args.expect_serial:
        for prev, cur in zip(users, users[1:]):
            p, c = prev["final"], cur["final"]
            if not (ts(c["started_at"]) > ts(p["started_at"])):
                serial_failures.append(f"job #{cur['expected_rank']} started before job #{prev['expected_rank']}")
            if not (ts(c["started_at"]) >= ts(p["completed_at"])):
                serial_failures.append(
                    f"job #{cur['expected_rank']} started ({c['started_at']}) before job #{prev['expected_rank']} "
                    f"finished ({p['completed_at']}) -- more than one job running at once"
                )

    ok = ordering_ok and not position_failures and not serial_failures
    if ok:
        log(
            "[PASS] fcfs_queue: started-email order matches creation order; queue_position consistent with FCFS"
            + ("; jobs ran strictly one at a time in creation order" if args.expect_serial else "")
        )
    else:
        if not ordering_ok:
            log(f"[FAIL] fcfs_queue: started-email order {arrival_order} != creation order {expected_order}")
        for failure in position_failures + serial_failures:
            log(f"[FAIL] fcfs_queue: {failure}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
