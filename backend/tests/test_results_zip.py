"""Unit tests for the password-protected results zip (app/results_zip.py)
and the download request schema. Run inside the backend image -- see
tests/run_backend_unit_tests.sh."""
import os
import sys
import zipfile

import pytest
import pyzipper
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ -> `import app.*`

from app.results_zip import build_encrypted_zip  # noqa: E402
from app.schemas import DownloadRequest  # noqa: E402

PASSWORD = "correct-horse-1"


@pytest.fixture
def results_dir(tmp_path):
    root = tmp_path / "results"
    (root / "result_DIETNET_RESULTS_BY_MODEL").mkdir(parents=True)
    (root / "result_results_table.tsv").write_text("Sample\tMissing rate (%)\nid1\t0.5\n")
    (root / "result_job_log.txt").write_text("Diet Network ancestry inference -- job log\n")
    (root / "result_DIETNET_RESULTS_BY_MODEL" / "result_model1_1_infered.npz").write_bytes(os.urandom(4096))
    return root


def test_zip_opens_with_correct_password_and_keeps_layout(results_dir, tmp_path):
    dest = tmp_path / "out.zip"
    build_encrypted_zip(str(results_dir), str(dest), PASSWORD)

    with pyzipper.AESZipFile(dest) as zf:
        zf.setpassword(PASSWORD.encode())
        names = sorted(zf.namelist())
        assert names == [
            "result_DIETNET_RESULTS_BY_MODEL/result_model1_1_infered.npz",
            "result_job_log.txt",
            "result_results_table.tsv",
        ]
        assert zf.read("result_results_table.tsv") == (results_dir / "result_results_table.tsv").read_bytes()
        npz = "result_DIETNET_RESULTS_BY_MODEL/result_model1_1_infered.npz"
        assert zf.read(npz) == (results_dir / npz).read_bytes()


def test_every_entry_is_aes_encrypted(results_dir, tmp_path):
    dest = tmp_path / "out.zip"
    build_encrypted_zip(str(results_dir), str(dest), PASSWORD)

    with pyzipper.AESZipFile(dest) as zf:
        for info in zf.infolist():
            assert info.flag_bits & 0x1, f"{info.filename} is not encrypted"
            # WinZip AES extra field, strength 3 = AES-256 (pyzipper reports
            # the inner compression in compress_type, not the 99 AES marker).
            assert info.wz_aes_vendor_id == b"AE", f"{info.filename} is not WinZip-AES"
            assert info.wz_aes_strength == 3, f"{info.filename} is not AES-256"


def test_wrong_password_is_rejected(results_dir, tmp_path):
    dest = tmp_path / "out.zip"
    build_encrypted_zip(str(results_dir), str(dest), PASSWORD)

    with pyzipper.AESZipFile(dest) as zf:
        zf.setpassword(b"wrong-password")
        with pytest.raises(RuntimeError):
            zf.read("result_job_log.txt")


def test_contents_unreadable_without_password(results_dir, tmp_path):
    dest = tmp_path / "out.zip"
    build_encrypted_zip(str(results_dir), str(dest), PASSWORD)

    # Plaintext must not appear anywhere in the archive bytes.
    assert b"Diet Network ancestry inference" not in dest.read_bytes()
    # And the stdlib reader can't extract it.
    with zipfile.ZipFile(dest) as zf:
        with pytest.raises((RuntimeError, NotImplementedError)):
            zf.read("result_job_log.txt")


def test_short_password_rejected(results_dir, tmp_path):
    with pytest.raises(ValueError):
        build_encrypted_zip(str(results_dir), str(tmp_path / "out.zip"), "short")


def test_download_request_password_length():
    assert DownloadRequest(password="12345678").password == "12345678"
    with pytest.raises(ValidationError):
        DownloadRequest(password="1234567")
    with pytest.raises(ValidationError):
        DownloadRequest(password="x" * 129)
