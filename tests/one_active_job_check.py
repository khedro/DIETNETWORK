#!/usr/bin/env python3
"""Verifies the one-active-job-per-user gate in backend/app/routers/uploads.py
(create_upload): a user with a queued/running job gets a 409 on a second
upload, and the gate releases once that job reaches a terminal state.

Usage: one_active_job_check.py --base-url URL --mailhog-url URL
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import TestFailure, signup_verify_login, unique_email, upload_plink, wait_for_status  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(REPO_ROOT, "dataTest", "fixtures", "low_overlap")  # fails fast; status just needs to be non-terminal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mailhog-url", required=True)
    args = parser.parse_args()

    try:
        session = signup_verify_login(args.base_url, args.mailhog_url, unique_email("one-active-job"))

        job1 = upload_plink(session, args.base_url, FIXTURE)
        resp2 = session.post(
            f"{args.base_url}/uploads",
            files={
                "genotype_file": ("query.bed", open(FIXTURE + ".bed", "rb"), "application/octet-stream"),
                "bim_file": ("query.bim", open(FIXTURE + ".bim", "rb"), "application/octet-stream"),
                "fam_file": ("query.fam", open(FIXTURE + ".fam", "rb"), "application/octet-stream"),
            },
            data={"consent": "true"},
            timeout=60,
        )
        blocked = resp2.status_code == 409
        print(
            f"{'[PASS]' if blocked else '[FAIL]'} one_active_job: second upload while job1 non-terminal -> "
            f"{resp2.status_code} (expected 409): {resp2.text[:200]}"
        )

        wait_for_status(session, args.base_url, job1["id"], {"done", "failed"}, timeout=120)
        job3 = upload_plink(session, args.base_url, FIXTURE)  # raises TestFailure (non-201) if still blocked
        released = job3["id"] != job1["id"]
        print(f"{'[PASS]' if released else '[FAIL]'} one_active_job: gate released after job1 finished")

        ok = blocked and released
    except TestFailure as exc:
        print(f"[FAIL] one_active_job: {exc}")
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
