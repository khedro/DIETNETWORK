"""Password-protected results zip (specifications.docx: "Encryption avec
password"). AES-256 via pyzipper (WinZip AES format): the legacy ZipCrypto
scheme that Python's stdlib zipfile can read is too weak for genetic data.
AES zips open in 7-Zip, macOS Archive Utility / `unzip` from p7zip, and
Python's pyzipper -- not in Windows Explorer's built-in zip support.

Kept free of app settings/DB imports so it can be unit-tested on its own
(backend/tests/test_results_zip.py)."""
import os

import pyzipper

MIN_PASSWORD_LENGTH = 8


def build_encrypted_zip(results_dir: str, dest_path: str, password: str) -> None:
    """Zips every file under results_dir, preserving subdirectories, with
    every entry AES-256 encrypted under `password`."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    with pyzipper.AESZipFile(
        dest_path, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.setencryption(pyzipper.WZ_AES, nbits=256)
        for root, _dirs, files in os.walk(results_dir):
            for name in sorted(files):
                full_path = os.path.join(root, name)
                zf.write(full_path, arcname=os.path.relpath(full_path, results_dir))
