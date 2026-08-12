#!/bin/bash
# Downloads the pretrained Diet Network weights + SNP files from Zenodo
# record 16943452 (DN_MODELS/ and DN_SNPS/) ONCE, at worker image build
# time. Never call this at request/runtime -- see deployPlan.md point 5.
#
# Usage: fetch_zenodo_models.sh <dest_dir>
set -euo pipefail

DEST="${1:?Usage: fetch_zenodo_models.sh <dest_dir>}"
ZENODO_RECORD="16943452"
ZENODO_API="https://zenodo.org/api/records/${ZENODO_RECORD}"

mkdir -p "$DEST"
cd "$DEST"

echo "Fetching file list for Zenodo record ${ZENODO_RECORD}..."
curl -fsSL "$ZENODO_API" -o record.json

# Each Zenodo record file has a direct download link at .files[].links.self
python3 - "$DEST" <<'PYEOF'
import json
import os
import sys
import urllib.request

dest = sys.argv[1]
with open(os.path.join(dest, "record.json")) as f:
    record = json.load(f)

for entry in record.get("files", []):
    url = entry["links"]["self"]
    name = entry["key"]
    out_path = os.path.join(dest, name)
    print(f"Downloading {name} ...")
    urllib.request.urlretrieve(url, out_path)
PYEOF

rm -f record.json

# The Zenodo record is expected to contain (possibly as a zip/tar) the
# DN_MODELS/ and DN_SNPS/ directories used by infer.sh. Unpack any archives
# so the final layout is: $DEST/DN_MODELS/*.pt|*.npz and $DEST/DN_SNPS/*.txt
for archive in *.zip; do
    [ -e "$archive" ] || continue
    echo "Unpacking $archive ..."
    unzip -o "$archive" -d "$DEST"
    rm -f "$archive"
done
for archive in *.tar.gz *.tgz; do
    [ -e "$archive" ] || continue
    echo "Unpacking $archive ..."
    tar -xzf "$archive" -C "$DEST"
    rm -f "$archive"
done

if [ ! -d "$DEST/DN_MODELS" ] || [ ! -d "$DEST/DN_SNPS" ]; then
    echo "WARNING: expected $DEST/DN_MODELS and $DEST/DN_SNPS after unpacking." >&2
    echo "Inspect the Zenodo record layout (it may have changed) and adjust this script." >&2
    ls -la "$DEST" >&2
    exit 1
fi

echo "Diet Network model files ready at $DEST"
